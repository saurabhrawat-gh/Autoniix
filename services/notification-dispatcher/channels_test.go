package dispatcher

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// helper: shared HTTP client with tight timeout so tests stay fast.
func newTestClient() *http.Client {
	return &http.Client{Timeout: 2 * time.Second}
}

func TestBrowserChannel_AlwaysSucceeds(t *testing.T) {
	t.Parallel()
	ch := &BrowserChannel{}
	resp, err := ch.Send(context.Background(),
		NotificationPayload{EventType: "test.event", Severity: "info", Title: "hi"},
		nil,
	)
	if err != nil {
		t.Fatalf("browser send: %v", err)
	}
	if resp["info"] != "via_notification_center" {
		t.Fatalf("unexpected response: %v", resp)
	}
}

func TestEmailChannel_AlwaysFails(t *testing.T) {
	t.Parallel()
	ch := &EmailChannel{}
	_, err := ch.Send(context.Background(), NotificationPayload{}, nil)
	if err == nil {
		t.Fatal("email channel should return not-configured error")
	}
}

func TestSlackChannel_MissingWebhookIsError(t *testing.T) {
	// No t.Parallel — t.Setenv is not compatible with parallel tests.
	t.Setenv("SLACK_WEBHOOK_URL", "")
	ch := &SlackChannel{HTTP: newTestClient()}
	_, err := ch.Send(context.Background(),
		NotificationPayload{Severity: "info", Title: "x"},
		nil, // no webhook_url in config either
	)
	if err == nil {
		t.Fatal("expected missing-webhook error")
	}
}

func TestSlackChannel_PostsExpectedPayload(t *testing.T) {
	t.Parallel()

	// Capture the outbound payload so we can assert its shape.
	var received map[string]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(body, &received)
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	ch := &SlackChannel{HTTP: newTestClient()}
	resp, err := ch.Send(context.Background(),
		NotificationPayload{
			EventType: "test.event",
			Severity:  "error",
			Title:     "Something broke",
			Body:      "details",
			Payload:   map[string]any{"key": "value"},
		},
		map[string]any{"webhook_url": srv.URL},
	)
	if err != nil {
		t.Fatalf("slack send: %v", err)
	}
	if resp["status"] != 200 {
		t.Fatalf("expected status 200, got %v", resp["status"])
	}

	// Payload shape assertions — mirrors Python _send_slack.
	att, ok := received["attachments"].([]any)
	if !ok || len(att) != 1 {
		t.Fatalf("expected one attachment, got %v", received["attachments"])
	}
	a := att[0].(map[string]any)
	if a["color"] != severityColor["error"] {
		t.Errorf("color mismatch: got %v want %v", a["color"], severityColor["error"])
	}
	if a["title"] != "Something broke" {
		t.Errorf("title mismatch: %v", a["title"])
	}
	if a["footer"] != "event: test.event · severity: error" {
		t.Errorf("footer mismatch: %v", a["footer"])
	}
}

func TestWebhookChannel_MissingURLIsError(t *testing.T) {
	t.Parallel()
	ch := &WebhookChannel{HTTP: newTestClient()}
	_, err := ch.Send(context.Background(), NotificationPayload{}, nil)
	if err == nil {
		t.Fatal("expected missing-url error")
	}
}

func TestWebhookChannel_ForwardsNotificationBody(t *testing.T) {
	t.Parallel()

	var received NotificationPayload
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(body, &received)
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	ch := &WebhookChannel{HTTP: newTestClient()}
	_, err := ch.Send(context.Background(),
		NotificationPayload{EventType: "hello", Title: "T"},
		map[string]any{"url": srv.URL},
	)
	if err != nil {
		t.Fatalf("webhook send: %v", err)
	}
	if received.EventType != "hello" || received.Title != "T" {
		t.Fatalf("payload not forwarded verbatim: %+v", received)
	}
}

func TestWebhookChannel_NonOK_IsError(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		http.Error(w, "boom", http.StatusInternalServerError)
	}))
	defer srv.Close()

	ch := &WebhookChannel{HTTP: newTestClient()}
	_, err := ch.Send(context.Background(),
		NotificationPayload{EventType: "x"},
		map[string]any{"url": srv.URL},
	)
	if err == nil {
		t.Fatal("expected 500 to surface as error")
	}
}

func TestTruncate(t *testing.T) {
	t.Parallel()
	if got := truncate("abcdef", 3); got != "abc" {
		t.Errorf("truncate(6, 3) = %q", got)
	}
	if got := truncate("ab", 5); got != "ab" {
		t.Errorf("truncate(2, 5) = %q", got)
	}
}
