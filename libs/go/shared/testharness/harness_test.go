package testharness_test

import (
	"context"
	"testing"

	"github.com/autoniix/autoniix/go/shared/testharness"
)

func TestNewHarness(t *testing.T) {
	h := testharness.New(t, "research")
	if h.Server == nil {
		t.Fatal("expected Server to be non-nil")
	}
	if h.Conn == nil {
		t.Fatal("expected Conn to be non-nil")
	}
	if h.MockLLM == nil {
		t.Fatal("expected MockLLM to be non-nil")
	}
}

func TestMockLLMProvider(t *testing.T) {
	m := testharness.NewMockLLMProvider()

	t.Run("default response", func(t *testing.T) {
		resp, err := m.Complete(context.Background(), "some random prompt")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if resp == "" {
			t.Fatal("expected non-empty response")
		}
	})

	t.Run("research keyword response", func(t *testing.T) {
		resp, err := m.Complete(context.Background(), "please research this topic")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if resp == "" {
			t.Fatal("expected non-empty research response")
		}
	})

	t.Run("call count increments", func(t *testing.T) {
		m.Reset()
		m.Complete(context.Background(), "call 1")
		m.Complete(context.Background(), "call 2")
		if m.CallCount != 2 {
			t.Fatalf("expected CallCount=2, got %d", m.CallCount)
		}
	})

	t.Run("custom response", func(t *testing.T) {
		m.SetResponse("custom_keyword", `{"custom": true}`)
		resp, err := m.Complete(context.Background(), "this has custom_keyword in it")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if resp != `{"custom": true}` {
			t.Fatalf("expected custom response, got: %s", resp)
		}
	})
}
