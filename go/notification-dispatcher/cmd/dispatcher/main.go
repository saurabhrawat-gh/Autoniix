// Command notification-dispatcher runs the G1 Go microservice.
//
// Responsibility: poll notification_deliveries for stuck rows and
// retry delivery. Runs alongside Python's inline dispatcher without
// duplicating deliveries (thanks to StaleAfter + FOR UPDATE SKIP LOCKED).
package main

import (
	"context"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	shconfig "github.com/autoniix/autoniix/go/shared/config"
	shdb "github.com/autoniix/autoniix/go/shared/db"
	shhttp "github.com/autoniix/autoniix/go/shared/httpx"
	shlog "github.com/autoniix/autoniix/go/shared/log"

	dispatcher "github.com/autoniix/autoniix/go/notification-dispatcher"
)

// appConfig maps env vars for this service. Namespace: NDISP_*.
type appConfig struct {
	// DatabaseURL is the shared app postgres. Falls back to DATABASE_URL if unset.
	DatabaseURL string `envconfig:"DATABASE_URL"`
	// HTTPAddr is where /health and /ready listen.
	HTTPAddr string `envconfig:"HTTP_ADDR" default:":8090"`
	// PollIntervalMS is how often to poll for stuck deliveries.
	PollIntervalMS int `envconfig:"POLL_INTERVAL_MS" default:"15000"`
	// StaleAfterMS is how old a queued row must be before we claim it.
	StaleAfterMS int `envconfig:"STALE_AFTER_MS" default:"60000"`
	// BatchSize caps rows claimed per tick.
	BatchSize int `envconfig:"BATCH_SIZE" default:"50"`
	// MaxAttempts is total delivery attempts before permanent failure.
	MaxAttempts int `envconfig:"MAX_ATTEMPTS" default:"3"`
}

func main() {
	log := shlog.New("notification-dispatcher")
	defer func() { _ = log.Sync() }()

	var cfg appConfig
	shconfig.MustLoad("NDISP", &cfg)
	// DATABASE_URL fallback is common convention.
	if cfg.DatabaseURL == "" {
		cfg.DatabaseURL = os.Getenv("DATABASE_URL")
	}

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	pool, err := shdb.Open(ctx, shdb.DefaultConfig(cfg.DatabaseURL))
	if err != nil {
		log.Fatalw("db.connect.failed", "err", err)
	}
	defer pool.Close()

	dcfg := dispatcher.Default()
	dcfg.PollInterval = time.Duration(cfg.PollIntervalMS) * time.Millisecond
	dcfg.StaleAfter = time.Duration(cfg.StaleAfterMS) * time.Millisecond
	dcfg.BatchSize = cfg.BatchSize
	dcfg.MaxAttempts = cfg.MaxAttempts

	channels := dispatcher.DefaultChannels(&http.Client{Timeout: dcfg.HTTPTimeout})
	d := dispatcher.New(pool, log, dcfg, channels)

	// HTTP surface: liveness + readiness only. This is a worker, not an API.
	r := shhttp.NewRouter()
	r.Get("/health", shhttp.Health("notification-dispatcher"))
	r.Get("/ready", shhttp.Ready(func() error { return pool.Ping(ctx) }))

	srv := &http.Server{
		Addr:         cfg.HTTPAddr,
		Handler:      r,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 5 * time.Second,
	}
	go func() {
		log.Infow("http.listen", "addr", cfg.HTTPAddr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Errorw("http.listen.failed", "err", err)
			cancel()
		}
	}()

	log.Infow("dispatcher.start",
		"poll_ms", cfg.PollIntervalMS,
		"stale_ms", cfg.StaleAfterMS,
		"batch", cfg.BatchSize,
	)
	if err := d.Run(ctx); err != nil && !errors.Is(err, context.Canceled) {
		log.Errorw("dispatcher.exit", "err", err)
	}

	shutdownCtx, cancelShutdown := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancelShutdown()
	_ = srv.Shutdown(shutdownCtx)
	log.Infow("dispatcher.stopped")
}
