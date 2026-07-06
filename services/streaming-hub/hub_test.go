package streaminghub_test

import (
	"context"
	"testing"
	"time"

	streamingv1 "github.com/autoniix/autoniix/gen/go/autoniix/streaming/v1"
	streaminghub "github.com/autoniix/autoniix/services/streaming-hub"
	"go.uber.org/zap"
)

func newTestHub() *streaminghub.Hub {
	return streaminghub.NewHub(nil, zap.NewNop().Sugar())
}

func TestHub_SubscribeUnsubscribe(t *testing.T) {
	hub := newTestHub()
	req := &streamingv1.SubscribeRequest{WorkspaceId: "ws1"}
	id, ch := hub.Subscribe(req)
	if id == "" {
		t.Fatal("expected non-empty subscriber id")
	}
	if ch == nil {
		t.Fatal("expected non-nil channel")
	}
	hub.Unsubscribe(id)
	// channel should be closed after unsubscribe
	select {
	case _, ok := <-ch:
		if ok {
			t.Fatal("channel should be closed after unsubscribe")
		}
	case <-time.After(100 * time.Millisecond):
		t.Fatal("channel not closed after unsubscribe")
	}
}

func TestHub_Publish_FanoutByWorkspace(t *testing.T) {
	hub := newTestHub()

	id1, ch1 := hub.Subscribe(&streamingv1.SubscribeRequest{WorkspaceId: "ws1"})
	id2, ch2 := hub.Subscribe(&streamingv1.SubscribeRequest{WorkspaceId: "ws2"})
	defer hub.Unsubscribe(id1)
	defer hub.Unsubscribe(id2)

	evt := &streamingv1.Event{Type: "job.update", WorkspaceId: "ws1"}
	if err := hub.Publish(context.Background(), evt); err != nil {
		t.Fatalf("publish error: %v", err)
	}

	select {
	case got := <-ch1:
		if got.Type != "job.update" {
			t.Errorf("got type %q, want job.update", got.Type)
		}
	case <-time.After(200 * time.Millisecond):
		t.Fatal("ws1 subscriber did not receive event")
	}

	select {
	case <-ch2:
		t.Fatal("ws2 subscriber should not have received ws1 event")
	case <-time.After(50 * time.Millisecond):
		// expected: no event
	}
}

func TestHub_Publish_BroadcastNoFilter(t *testing.T) {
	hub := newTestHub()
	id, ch := hub.Subscribe(&streamingv1.SubscribeRequest{WorkspaceId: ""})
	defer hub.Unsubscribe(id)

	evt := &streamingv1.Event{Type: "system.ping", WorkspaceId: "any"}
	_ = hub.Publish(context.Background(), evt)

	select {
	case got := <-ch:
		if got.Type != "system.ping" {
			t.Errorf("got %q, want system.ping", got.Type)
		}
	case <-time.After(200 * time.Millisecond):
		t.Fatal("subscriber with no workspace filter should receive all events")
	}
}

func TestHub_Publish_EventTypeFilter(t *testing.T) {
	hub := newTestHub()
	id, ch := hub.Subscribe(&streamingv1.SubscribeRequest{
		WorkspaceId: "ws1",
		EventTypes:  []string{"job.done"},
	})
	defer hub.Unsubscribe(id)

	_ = hub.Publish(context.Background(), &streamingv1.Event{Type: "job.started", WorkspaceId: "ws1"})
	_ = hub.Publish(context.Background(), &streamingv1.Event{Type: "job.done", WorkspaceId: "ws1"})

	var received []string
	deadline := time.After(300 * time.Millisecond)
loop:
	for {
		select {
		case evt, ok := <-ch:
			if !ok {
				break loop
			}
			received = append(received, evt.Type)
		case <-deadline:
			break loop
		}
	}

	if len(received) != 1 || received[0] != "job.done" {
		t.Errorf("got events %v, want [job.done]", received)
	}
}
