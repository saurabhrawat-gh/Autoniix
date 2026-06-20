// Package testharness provides a reusable in-process test harness for Go
// microservices (Research, Script, Voice, Image, etc.).
//
// Per HARNESS-ENGINEERING-PLAN.md Week 3 Day 1-2.
//
// Usage:
//
//	func TestMyService(t *testing.T) {
//	    h := testharness.New(t, "research")
//	    defer h.Close()
//
//	    resp, err := h.Client.Research(ctx, &pb.ResearchRequest{Topic: "AI"})
//	    assert.NoError(t, err)
//	    assert.NotEmpty(t, resp.Summary)
//	}
package testharness

import (
	"context"
	"net"
	"testing"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/test/bufconn"
)

const bufSize = 1024 * 1024 // 1 MiB in-memory buffer

// ServiceHarness is an in-process gRPC test harness.
// It starts a gRPC server over bufconn (no TCP port needed).
type ServiceHarness struct {
	t          *testing.T
	ServiceName string

	// Server is the in-process gRPC server.
	Server *grpc.Server

	// Conn is the client connection to the in-process server.
	Conn *grpc.ClientConn

	// MockLLM is the shared mock LLM provider.
	MockLLM *MockLLMProvider

	listener *bufconn.Listener
}

// New creates a new ServiceHarness for the given service name.
// Registers the mock LLM provider automatically.
func New(t *testing.T, serviceName string) *ServiceHarness {
	t.Helper()

	lis := bufconn.Listen(bufSize)
	srv := grpc.NewServer()

	h := &ServiceHarness{
		t:           t,
		ServiceName: serviceName,
		Server:      srv,
		MockLLM:     NewMockLLMProvider(),
		listener:    lis,
	}

	// Start server in background
	go func() {
		if err := srv.Serve(lis); err != nil && err != grpc.ErrServerStopped {
			t.Logf("testharness: server error: %v", err)
		}
	}()

	// Connect client via bufconn dialer
	conn, err := grpc.NewClient(
		"passthrough:///bufnet",
		grpc.WithContextDialer(func(ctx context.Context, _ string) (net.Conn, error) {
			return lis.DialContext(ctx)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("testharness: failed to create client connection: %v", err)
	}
	h.Conn = conn

	t.Cleanup(func() { h.Close() })

	t.Logf("testharness: %s started (in-process bufconn)", serviceName)
	return h
}

// Close gracefully stops the server and closes the client connection.
func (h *ServiceHarness) Close() {
	if h.Conn != nil {
		h.Conn.Close()
	}
	if h.Server != nil {
		h.Server.GracefulStop()
	}
	if h.listener != nil {
		h.listener.Close()
	}
}

// MockLLMProvider is a fake LLM provider for use in tests.
// Responses are deterministic (keyed by the prompt hash).
type MockLLMProvider struct {
	responses map[string]string
	CallCount int
}

// NewMockLLMProvider creates a MockLLMProvider with default responses.
func NewMockLLMProvider() *MockLLMProvider {
	return &MockLLMProvider{
		responses: map[string]string{
			"default": `{"result": "mock_response", "score": 8.5, "pass": true}`,
			"research": `{"selected_topic": "Mock Topic", "title_candidates": ["Title 1", "Title 2"], "key_facts": ["Fact 1", "Fact 2"]}`,
			"script":   `{"title": "Mock Script", "segments": [{"id": "seg_1", "section": "hook", "text": "Mock hook.", "duration_s": 5}], "total_duration_s": 60}`,
		},
	}
}

// Complete returns a deterministic mock LLM response.
func (m *MockLLMProvider) Complete(ctx context.Context, prompt string) (string, error) {
	m.CallCount++

	for key, resp := range m.responses {
		if key != "default" && containsSubstring(prompt, key) {
			return resp, nil
		}
	}
	return m.responses["default"], nil
}

// SetResponse overrides the default response for a given keyword.
func (m *MockLLMProvider) SetResponse(keyword, response string) {
	m.responses[keyword] = response
}

// Reset clears call counts and custom responses.
func (m *MockLLMProvider) Reset() {
	m.CallCount = 0
	m.responses = map[string]string{
		"default": `{"result": "mock_response", "score": 8.5, "pass": true}`,
	}
}

func containsSubstring(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && containsAt(s, substr))
}

func containsAt(s, sub string) bool {
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
