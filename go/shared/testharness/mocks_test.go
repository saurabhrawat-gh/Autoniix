package testharness_test

import (
	"context"
	"testing"
	"time"

	"github.com/autoniix/autoniix/go/shared/testharness"
)

// ── MockRedisClient ──────────────────────────────────────────────────────────

func TestMockRedisSetGet(t *testing.T) {
	r := testharness.NewMockRedisClient()
	ctx := context.Background()

	if err := r.Set(ctx, "key1", "value1", 0); err != nil {
		t.Fatalf("Set: %v", err)
	}
	v, ok := r.Get(ctx, "key1")
	if !ok || v != "value1" {
		t.Fatalf("Get: expected value1, got %q (ok=%v)", v, ok)
	}
}

func TestMockRedisExpiry(t *testing.T) {
	r := testharness.NewMockRedisClient()
	ctx := context.Background()

	r.Set(ctx, "expiring", "soon", 1*time.Millisecond)
	time.Sleep(5 * time.Millisecond)
	_, ok := r.Get(ctx, "expiring")
	if ok {
		t.Fatal("expected expired key to be absent")
	}
}

func TestMockRedisDel(t *testing.T) {
	r := testharness.NewMockRedisClient()
	ctx := context.Background()

	r.Set(ctx, "a", "1", 0)
	r.Set(ctx, "b", "2", 0)
	count := r.Del(ctx, "a", "b", "missing")
	if count != 2 {
		t.Fatalf("expected Del to return 2, got %d", count)
	}
	if _, ok := r.Get(ctx, "a"); ok {
		t.Fatal("key 'a' should have been deleted")
	}
}

func TestMockRedisIncr(t *testing.T) {
	r := testharness.NewMockRedisClient()
	ctx := context.Background()

	v1 := r.Incr(ctx, "counter")
	v2 := r.Incr(ctx, "counter")
	v3 := r.Incr(ctx, "counter")
	if v1 != 1 || v2 != 2 || v3 != 3 {
		t.Fatalf("expected 1,2,3 got %d,%d,%d", v1, v2, v3)
	}
}

func TestMockRedisPubSub(t *testing.T) {
	r := testharness.NewMockRedisClient()
	ctx := context.Background()

	ch := r.Subscribe(ctx, "events")
	r.Publish(ctx, "events", "hello")

	select {
	case msg := <-ch:
		if msg != "hello" {
			t.Fatalf("expected 'hello', got %q", msg)
		}
	case <-time.After(100 * time.Millisecond):
		t.Fatal("timed out waiting for pub/sub message")
	}
}

func TestMockRedisReset(t *testing.T) {
	r := testharness.NewMockRedisClient()
	ctx := context.Background()

	r.Set(ctx, "x", "y", 0)
	r.Reset()
	if _, ok := r.Get(ctx, "x"); ok {
		t.Fatal("expected empty store after Reset")
	}
}

// ── MockTemporalClient ───────────────────────────────────────────────────────

func TestMockTemporalExecute(t *testing.T) {
	tc := testharness.NewMockTemporalClient()
	ctx := context.Background()

	run, err := tc.ExecuteWorkflow(ctx, "research_workflow", "wf-001")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if run.WorkflowID != "wf-001" {
		t.Fatalf("expected wf-001, got %s", run.WorkflowID)
	}
	if run.Result == nil {
		t.Fatal("expected non-nil result")
	}
}

func TestMockTemporalCustomHandler(t *testing.T) {
	tc := testharness.NewMockTemporalClient()
	ctx := context.Background()

	tc.RegisterWorkflow("custom", func(args ...interface{}) (interface{}, error) {
		return map[string]interface{}{"custom": true}, nil
	})

	run, err := tc.ExecuteWorkflow(ctx, "custom", "wf-002")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	result, ok := run.Result.(map[string]interface{})
	if !ok || result["custom"] != true {
		t.Fatalf("expected custom result, got %v", run.Result)
	}
}

func TestMockTemporalGetWorkflow(t *testing.T) {
	tc := testharness.NewMockTemporalClient()
	ctx := context.Background()

	tc.ExecuteWorkflow(ctx, "my_workflow", "wf-003")
	run, ok := tc.GetWorkflow(ctx, "wf-003")
	if !ok {
		t.Fatal("expected to find wf-003")
	}
	if run.WorkflowID != "wf-003" {
		t.Fatalf("expected wf-003, got %s", run.WorkflowID)
	}
}

func TestMockTemporalReset(t *testing.T) {
	tc := testharness.NewMockTemporalClient()
	ctx := context.Background()

	tc.ExecuteWorkflow(ctx, "wf", "wf-reset")
	tc.Reset()
	if _, ok := tc.GetWorkflow(ctx, "wf-reset"); ok {
		t.Fatal("expected empty state after Reset")
	}
}

// ── MockObjectStore ──────────────────────────────────────────────────────────

func TestMockObjectStorePutGet(t *testing.T) {
	s := testharness.NewMockObjectStore()
	ctx := context.Background()

	data := []byte("hello world")
	if err := s.Put(ctx, "bucket1", "file.txt", data, "text/plain"); err != nil {
		t.Fatalf("Put: %v", err)
	}

	got, ok := s.Get(ctx, "bucket1", "file.txt")
	if !ok {
		t.Fatal("expected key to exist")
	}
	if string(got) != "hello world" {
		t.Fatalf("expected 'hello world', got %q", got)
	}
}

func TestMockObjectStoreDelete(t *testing.T) {
	s := testharness.NewMockObjectStore()
	ctx := context.Background()

	s.Put(ctx, "b", "k", []byte("x"), "")
	s.Delete(ctx, "b", "k")
	if _, ok := s.Get(ctx, "b", "k"); ok {
		t.Fatal("expected key to be deleted")
	}
}

func TestMockObjectStoreList(t *testing.T) {
	s := testharness.NewMockObjectStore()
	ctx := context.Background()

	s.Put(ctx, "b", "img/a.png", []byte{}, "image/png")
	s.Put(ctx, "b", "img/b.png", []byte{}, "image/png")
	s.Put(ctx, "b", "doc/c.pdf", []byte{}, "application/pdf")

	keys := s.List(ctx, "b", "img/")
	if len(keys) != 2 {
		t.Fatalf("expected 2 img/ keys, got %d", len(keys))
	}
}

func TestMockObjectStorePresignedURL(t *testing.T) {
	s := testharness.NewMockObjectStore()
	ctx := context.Background()

	url, err := s.PresignedURL(ctx, "bucket", "key.png", time.Hour)
	if err != nil {
		t.Fatalf("PresignedURL: %v", err)
	}
	if url == "" {
		t.Fatal("expected non-empty URL")
	}
}

// ── MockEmailSender ──────────────────────────────────────────────────────────

func TestMockEmailSend(t *testing.T) {
	e := testharness.NewMockEmailSender()
	ctx := context.Background()

	e.Send(ctx, "alice@example.com", "Welcome", "Hello Alice!")

	mail := e.LastEmailTo("alice@example.com")
	if mail == nil {
		t.Fatal("expected to find sent email")
	}
	if mail.Subject != "Welcome" {
		t.Fatalf("expected subject 'Welcome', got %q", mail.Subject)
	}
}

func TestMockEmailLastEmailMissing(t *testing.T) {
	e := testharness.NewMockEmailSender()
	if mail := e.LastEmailTo("nobody@example.com"); mail != nil {
		t.Fatal("expected nil for unknown recipient")
	}
}

// ── FullServiceMocks ─────────────────────────────────────────────────────────

func TestFullServiceMocksReset(t *testing.T) {
	m := testharness.NewFullServiceMocks()
	ctx := context.Background()

	m.Redis.Set(ctx, "x", "y", 0)
	m.Email.Send(ctx, "a@b.com", "s", "b")
	m.Reset()

	if _, ok := m.Redis.Get(ctx, "x"); ok {
		t.Fatal("Redis should be empty after Reset")
	}
	if m.Email.LastEmailTo("a@b.com") != nil {
		t.Fatal("Email should be empty after Reset")
	}
}
