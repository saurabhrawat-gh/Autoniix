package dispatcher

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

// Channel is a single delivery target (slack, webhook, browser, email).
type Channel interface {
	// Send delivers the notification and returns a response summary.
	// Any non-nil error is treated as a delivery failure.
	Send(ctx context.Context, n NotificationPayload, cfg map[string]any) (map[string]any, error)
}

// ChannelSet is a name→Channel lookup used by the dispatcher.
type ChannelSet map[string]Channel

// DefaultChannels returns the production channel set: slack, webhook,
// browser (no-op — served by the notification center itself),
// and a stub email channel that always fails until real SMTP is wired.
func DefaultChannels(httpClient *http.Client) ChannelSet {
	if httpClient == nil {
		httpClient = &http.Client{Timeout: 10 * time.Second}
	}
	return ChannelSet{
		"slack":   &SlackChannel{HTTP: httpClient},
		"webhook": &WebhookChannel{HTTP: httpClient},
		"browser": &BrowserChannel{},
		"email":   &EmailChannel{},
	}
}

// SlackChannel posts to a Slack Incoming Webhook. Config keys:
//   - webhook_url (preferred)
//
// Fallback: SLACK_WEBHOOK_URL env var if config has none.
type SlackChannel struct {
	HTTP *http.Client
}

// severityColor mirrors the color map in Python's _send_slack.
var severityColor = map[string]string{
	"info":     "#3aa3e3",
	"warn":     "#f0b429",
	"error":    "#e64980",
	"critical": "#c92a2a",
}

// Send posts a Slack attachment matching the Python payload byte-for-byte
// so operators see identical formatting regardless of dispatcher.
func (s *SlackChannel) Send(ctx context.Context, n NotificationPayload, cfg map[string]any) (map[string]any, error) {
	webhook, _ := cfg["webhook_url"].(string)
	if webhook == "" {
		webhook = os.Getenv("SLACK_WEBHOOK_URL")
	}
	if webhook == "" {
		return nil, fmt.Errorf("no slack webhook configured")
	}

	color, ok := severityColor[n.Severity]
	if !ok {
		color = "#888"
	}

	// Build fields — cap at 8, truncate value to 240 chars — matches Python.
	fields := make([]map[string]any, 0, 8)
	for k, v := range n.Payload {
		val := fmt.Sprintf("%v", v)
		if len(val) > 240 {
			val = val[:240]
		}
		fields = append(fields, map[string]any{
			"title": k,
			"value": val,
			"short": true,
		})
		if len(fields) == 8 {
			break
		}
	}

	body := map[string]any{
		"attachments": []map[string]any{{
			"color":  color,
			"title":  n.Title,
			"text":   n.Body,
			"fields": fields,
			"footer": fmt.Sprintf("event: %s · severity: %s", n.EventType, n.Severity),
		}},
	}

	return postJSON(ctx, s.HTTP, webhook, body)
}

// WebhookChannel POSTs the raw notification JSON to a configured URL.
type WebhookChannel struct {
	HTTP *http.Client
}

func (w *WebhookChannel) Send(ctx context.Context, n NotificationPayload, cfg map[string]any) (map[string]any, error) {
	url, _ := cfg["url"].(string)
	if url == "" {
		return nil, fmt.Errorf("no webhook url configured")
	}
	return postJSON(ctx, w.HTTP, url, n)
}

// BrowserChannel is served by the notification center itself — the
// row exists so the UI can render it. Delivery is a no-op success.
type BrowserChannel struct{}

func (b *BrowserChannel) Send(_ context.Context, _ NotificationPayload, _ map[string]any) (map[string]any, error) {
	return map[string]any{"info": "via_notification_center"}, nil
}

// EmailChannel is a placeholder until SMTP is wired. Matches Python behavior.
type EmailChannel struct{}

func (e *EmailChannel) Send(_ context.Context, _ NotificationPayload, _ map[string]any) (map[string]any, error) {
	return nil, fmt.Errorf("email channel not configured")
}

// postJSON is a small helper shared by slack + webhook channels.
func postJSON(ctx context.Context, client *http.Client, url string, body any) (map[string]any, error) {
	buf, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(buf))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if resp.StatusCode >= 400 {
		return map[string]any{"status": resp.StatusCode}, fmt.Errorf("http %d: %s", resp.StatusCode, truncate(string(respBody), 240))
	}
	return map[string]any{"status": resp.StatusCode}, nil
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}
