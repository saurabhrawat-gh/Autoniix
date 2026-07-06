// Package dispatcher implements the notification retry poller.
//
// Design: this is an ADDITIVE service. Python's src/services/dashboard/v2/_notify.py
// still creates notification_deliveries rows and attempts primary delivery
// synchronously. This dispatcher polls for stuck rows (status='queued'
// older than StaleAfter, or status='failed' with attempts < MaxAttempts)
// and retries them. Enabling this dispatcher does NOT change Python
// behavior — it only picks up failures that Python left behind.
//
// A future migration (tracked separately) will remove Python's inline
// dispatch and let this service own the primary path too.
package dispatcher

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"go.uber.org/zap"
)

// Config controls the poller's cadence and delivery limits.
type Config struct {
	// PollInterval is how often the poller wakes to look for work.
	PollInterval time.Duration
	// StaleAfter is the minimum age a queued row must reach before this
	// service will claim it. Prevents racing Python's inline delivery.
	StaleAfter time.Duration
	// BatchSize caps how many rows are claimed per tick.
	BatchSize int
	// MaxAttempts is the total number of delivery attempts before a row
	// is left in status='failed' permanently.
	MaxAttempts int
	// HTTPTimeout bounds each outbound channel call.
	HTTPTimeout time.Duration
}

// Default returns production-safe defaults.
func Default() Config {
	return Config{
		PollInterval: 15 * time.Second,
		StaleAfter:   60 * time.Second,
		BatchSize:    50,
		MaxAttempts:  3,
		HTTPTimeout:  10 * time.Second,
	}
}

// Dispatcher polls notification_deliveries and retries stuck rows.
type Dispatcher struct {
	pool     *pgxpool.Pool
	log      *zap.SugaredLogger
	cfg      Config
	channels ChannelSet
}

// New builds a Dispatcher. Callers own the pool lifecycle.
func New(pool *pgxpool.Pool, log *zap.SugaredLogger, cfg Config, channels ChannelSet) *Dispatcher {
	return &Dispatcher{pool: pool, log: log, cfg: cfg, channels: channels}
}

// Run blocks until ctx is cancelled, polling every PollInterval.
func (d *Dispatcher) Run(ctx context.Context) error {
	t := time.NewTicker(d.cfg.PollInterval)
	defer t.Stop()

	// tick once immediately so tests don't have to wait a full interval
	if err := d.tick(ctx); err != nil {
		d.log.Warnw("dispatcher.tick.error", "err", err)
	}

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-t.C:
			if err := d.tick(ctx); err != nil {
				d.log.Warnw("dispatcher.tick.error", "err", err)
			}
		}
	}
}

// tick claims a batch of stale rows and dispatches them.
// Exported as a test hook — callers may invoke directly in unit tests.
func (d *Dispatcher) tick(ctx context.Context) error {
	rows, err := d.claim(ctx)
	if err != nil {
		return fmt.Errorf("claim: %w", err)
	}
	if len(rows) == 0 {
		return nil
	}
	d.log.Infow("dispatcher.batch", "size", len(rows))
	for _, r := range rows {
		d.deliver(ctx, r)
	}
	return nil
}

// deliveryRow captures the fields needed to redeliver a notification.
type deliveryRow struct {
	DeliveryID     int64
	NotificationID int64
	Channel        string
	Attempts       int16
	Config         map[string]any
	Notification   NotificationPayload
}

// NotificationPayload is the caller-facing notification shape. It mirrors
// the JSON that channels expect. Populated by claim() from a JOIN across
// notifications + notification_routes.
type NotificationPayload struct {
	EventType string         `json:"event_type"`
	Severity  string         `json:"severity"`
	Title     string         `json:"title"`
	Body      string         `json:"body"`
	Payload   map[string]any `json:"payload"`
	ChannelID string         `json:"channel_id,omitempty"`
	VideoID   string         `json:"video_id,omitempty"`
}

// claim locks up to BatchSize stale rows using FOR UPDATE SKIP LOCKED.
// A row is stale if status='queued' AND created_at < now() - StaleAfter,
// OR status='failed' AND attempts < MaxAttempts AND created_at < now() - StaleAfter.
// The rows are joined to their parent notification to build a payload.
func (d *Dispatcher) claim(ctx context.Context) ([]deliveryRow, error) {
	staleCutoff := time.Now().UTC().Add(-d.cfg.StaleAfter)

	// Two-step: fetch stale delivery ids, then join to notifications/routes.
	// Use FOR UPDATE SKIP LOCKED so concurrent dispatchers don't collide.
	tx, err := d.pool.Begin(ctx)
	if err != nil {
		return nil, err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	query := `
		SELECT d.id, d.notification_id, d.channel, d.attempts,
		       COALESCE(r.config, '{}'::jsonb) AS route_config,
		       n.event_type, n.severity, n.title,
		       COALESCE(n.body, '') AS body,
		       COALESCE(n.payload, '{}'::jsonb) AS payload,
		       COALESCE(n.channel_id, '') AS channel_id,
		       COALESCE(n.video_id, '') AS video_id
		  FROM notification_deliveries d
		  JOIN notifications n ON n.id = d.notification_id
		  LEFT JOIN notification_routes r ON r.id = d.route_id
		 WHERE (
		         (d.status = 'queued' AND d.created_at < $1)
		      OR (d.status = 'failed' AND d.attempts < $2 AND d.created_at < $1)
		       )
		 ORDER BY d.created_at ASC
		 LIMIT $3
		 FOR UPDATE OF d SKIP LOCKED
	`
	pgRows, err := tx.Query(ctx, query, staleCutoff, d.cfg.MaxAttempts, d.cfg.BatchSize)
	if err != nil {
		return nil, err
	}
	var out []deliveryRow
	for pgRows.Next() {
		var (
			dr           deliveryRow
			cfgBytes     []byte
			payloadBytes []byte
		)
		if err := pgRows.Scan(
			&dr.DeliveryID, &dr.NotificationID, &dr.Channel, &dr.Attempts,
			&cfgBytes,
			&dr.Notification.EventType, &dr.Notification.Severity, &dr.Notification.Title,
			&dr.Notification.Body, &payloadBytes,
			&dr.Notification.ChannelID, &dr.Notification.VideoID,
		); err != nil {
			pgRows.Close()
			return nil, err
		}
		_ = json.Unmarshal(cfgBytes, &dr.Config)
		_ = json.Unmarshal(payloadBytes, &dr.Notification.Payload)
		out = append(out, dr)
	}
	pgRows.Close()

	if len(out) == 0 {
		return nil, tx.Commit(ctx)
	}

	// Mark rows as 'sending' so nothing else picks them up between commit
	// and the individual UPDATE at the end of each delivery.
	ids := make([]int64, len(out))
	for i, r := range out {
		ids[i] = r.DeliveryID
	}
	if _, err := tx.Exec(ctx,
		`UPDATE notification_deliveries SET status='queued', attempts=attempts+1 WHERE id = ANY($1)`,
		ids,
	); err != nil {
		return nil, err
	}
	if err := tx.Commit(ctx); err != nil {
		return nil, err
	}
	return out, nil
}

// deliver invokes the channel and records the outcome.
func (d *Dispatcher) deliver(ctx context.Context, r deliveryRow) {
	ch, ok := d.channels[r.Channel]
	if !ok {
		d.markFailed(ctx, r.DeliveryID, fmt.Sprintf("unknown channel %q", r.Channel))
		return
	}
	dctx, cancel := context.WithTimeout(ctx, d.cfg.HTTPTimeout)
	defer cancel()

	resp, err := ch.Send(dctx, r.Notification, r.Config)
	if err != nil {
		d.markFailed(ctx, r.DeliveryID, err.Error())
		return
	}
	d.markSent(ctx, r.DeliveryID, resp)
}

func (d *Dispatcher) markSent(ctx context.Context, id int64, resp map[string]any) {
	body, _ := json.Marshal(resp)
	if _, err := d.pool.Exec(ctx,
		`UPDATE notification_deliveries
		    SET status='sent', response=$1::jsonb, sent_at=NOW()
		  WHERE id=$2`,
		body, id,
	); err != nil {
		d.log.Warnw("mark.sent.failed", "id", id, "err", err)
	}
}

func (d *Dispatcher) markFailed(ctx context.Context, id int64, errMsg string) {
	if _, err := d.pool.Exec(ctx,
		`UPDATE notification_deliveries
		    SET status='failed', error=$1, sent_at=NOW()
		  WHERE id=$2`,
		errMsg, id,
	); err != nil {
		d.log.Warnw("mark.failed.failed", "id", id, "err", err)
	}
}
