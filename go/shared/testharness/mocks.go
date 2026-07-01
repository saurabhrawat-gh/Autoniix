// Package testharness — additional mocks for Go microservice testing.
//
// Per HARNESS-ENGINEERING-PLAN.md Appendix.
//
// Provides lightweight in-process fakes for:
//   - MockRedisClient    — fake Redis (get/set/del/expire/publish)
//   - MockTemporalClient — fake Temporal workflow/activity execution
//   - MockObjectStore    — fake S3/MinIO (put/get/delete/list)
//   - MockEmailSender    — fake SMTP / SendGrid (captures sent emails)
//
// All mocks are goroutine-safe and reset-able between tests.
package testharness

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"
)

// MockRedisClient is an in-memory fake for Redis operations.
// Supports Get, Set, Del, Expire, Incr, Publish, and Subscribe.
type MockRedisClient struct {
	mu       sync.RWMutex
	store    map[string]string
	expiries map[string]time.Time
	pubsub   map[string][]chan string
	CallLog  []string
}

// NewMockRedisClient returns a fresh MockRedisClient.
func NewMockRedisClient() *MockRedisClient {
	return &MockRedisClient{
		store:    make(map[string]string),
		expiries: make(map[string]time.Time),
		pubsub:   make(map[string][]chan string),
	}
}

func (r *MockRedisClient) Set(_ context.Context, key, value string, ttl time.Duration) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.store[key] = value
	if ttl > 0 {
		r.expiries[key] = time.Now().Add(ttl)
	}
	r.CallLog = append(r.CallLog, fmt.Sprintf("SET %s", key))
	return nil
}

func (r *MockRedisClient) Get(_ context.Context, key string) (string, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	if exp, ok := r.expiries[key]; ok && time.Now().After(exp) {
		return "", false
	}
	v, ok := r.store[key]
	r.CallLog = append(r.CallLog, fmt.Sprintf("GET %s", key))
	return v, ok
}

func (r *MockRedisClient) Del(_ context.Context, keys ...string) int {
	r.mu.Lock()
	defer r.mu.Unlock()
	count := 0
	for _, k := range keys {
		if _, ok := r.store[k]; ok {
			delete(r.store, k)
			delete(r.expiries, k)
			count++
		}
		r.CallLog = append(r.CallLog, fmt.Sprintf("DEL %s", k))
	}
	return count
}

func (r *MockRedisClient) Incr(_ context.Context, key string) int64 {
	r.mu.Lock()
	defer r.mu.Unlock()
	cur := int64(0)
	if v, ok := r.store[key]; ok {
		fmt.Sscanf(v, "%d", &cur)
	}
	cur++
	r.store[key] = fmt.Sprintf("%d", cur)
	r.CallLog = append(r.CallLog, fmt.Sprintf("INCR %s", key))
	return cur
}

func (r *MockRedisClient) Publish(_ context.Context, channel, message string) error {
	r.mu.RLock()
	subs := append([]chan string{}, r.pubsub[channel]...)
	r.mu.RUnlock()
	for _, ch := range subs {
		select {
		case ch <- message:
		default:
		}
	}
	r.CallLog = append(r.CallLog, fmt.Sprintf("PUBLISH %s", channel))
	return nil
}

// Subscribe returns a channel that receives messages published to the given channel.
func (r *MockRedisClient) Subscribe(_ context.Context, channel string) <-chan string {
	ch := make(chan string, 32)
	r.mu.Lock()
	r.pubsub[channel] = append(r.pubsub[channel], ch)
	r.mu.Unlock()
	return ch
}

// Reset clears all stored state and call logs.
func (r *MockRedisClient) Reset() {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.store = make(map[string]string)
	r.expiries = make(map[string]time.Time)
	r.pubsub = make(map[string][]chan string)
	r.CallLog = nil
}

// WorkflowRun is a fake in-progress workflow execution.
type WorkflowRun struct {
	WorkflowID string
	RunID      string
	Result     interface{}
	Err        error
}

// MockTemporalClient fakes workflow/activity execution without a real Temporal cluster.
type MockTemporalClient struct {
	mu        sync.Mutex
	runs      map[string]*WorkflowRun
	callbacks map[string]func(args ...interface{}) (interface{}, error)
	CallLog   []string
	NextRunID int
}

// NewMockTemporalClient returns a fresh MockTemporalClient.
func NewMockTemporalClient() *MockTemporalClient {
	return &MockTemporalClient{
		runs:      make(map[string]*WorkflowRun),
		callbacks: make(map[string]func(args ...interface{}) (interface{}, error)),
	}
}

// RegisterWorkflow registers a fake handler for a workflow type.
func (tc *MockTemporalClient) RegisterWorkflow(name string, fn func(args ...interface{}) (interface{}, error)) {
	tc.mu.Lock()
	defer tc.mu.Unlock()
	tc.callbacks[name] = fn
}

// ExecuteWorkflow synchronously runs the registered fake and stores the run.
func (tc *MockTemporalClient) ExecuteWorkflow(_ context.Context, workflowType, workflowID string, args ...interface{}) (*WorkflowRun, error) {
	tc.mu.Lock()
	defer tc.mu.Unlock()

	tc.NextRunID++
	runID := fmt.Sprintf("run-%d", tc.NextRunID)
	tc.CallLog = append(tc.CallLog, fmt.Sprintf("EXECUTE %s/%s", workflowType, workflowID))

	run := &WorkflowRun{WorkflowID: workflowID, RunID: runID}

	if fn, ok := tc.callbacks[workflowType]; ok {
		result, err := fn(args...)
		run.Result = result
		run.Err = err
	} else {
		run.Result = map[string]interface{}{"status": "ok", "workflow": workflowType}
	}

	tc.runs[workflowID] = run
	return run, run.Err
}

// GetWorkflow returns the stored run for a given workflow ID.
func (tc *MockTemporalClient) GetWorkflow(_ context.Context, workflowID string) (*WorkflowRun, bool) {
	tc.mu.Lock()
	defer tc.mu.Unlock()
	run, ok := tc.runs[workflowID]
	return run, ok
}

// Reset clears all stored state.
func (tc *MockTemporalClient) Reset() {
	tc.mu.Lock()
	defer tc.mu.Unlock()
	tc.runs = make(map[string]*WorkflowRun)
	tc.callbacks = make(map[string]func(args ...interface{}) (interface{}, error))
	tc.CallLog = nil
	tc.NextRunID = 0
}

// ObjectMeta holds metadata for a stored object.
type ObjectMeta struct {
	Key         string
	Data        []byte
	ContentType string
	StoredAt    time.Time
}

// MockObjectStore fakes S3/MinIO for services that upload/download assets.
type MockObjectStore struct {
	mu      sync.RWMutex
	objects map[string]*ObjectMeta
	CallLog []string
}

// NewMockObjectStore returns a fresh MockObjectStore.
func NewMockObjectStore() *MockObjectStore {
	return &MockObjectStore{objects: make(map[string]*ObjectMeta)}
}

func (s *MockObjectStore) Put(_ context.Context, bucket, key string, data []byte, contentType string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	fullKey := bucket + "/" + key
	s.objects[fullKey] = &ObjectMeta{Key: key, Data: data, ContentType: contentType, StoredAt: time.Now()}
	s.CallLog = append(s.CallLog, fmt.Sprintf("PUT %s", fullKey))
	return nil
}

func (s *MockObjectStore) Get(_ context.Context, bucket, key string) ([]byte, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	obj, ok := s.objects[bucket+"/"+key]
	if !ok {
		return nil, false
	}
	s.CallLog = append(s.CallLog, fmt.Sprintf("GET %s/%s", bucket, key))
	return obj.Data, true
}

func (s *MockObjectStore) Delete(_ context.Context, bucket, key string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.objects, bucket+"/"+key)
	s.CallLog = append(s.CallLog, fmt.Sprintf("DELETE %s/%s", bucket, key))
	return nil
}

// List returns all object keys in a bucket with an optional prefix filter.
func (s *MockObjectStore) List(_ context.Context, bucket, prefix string) []string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	var keys []string
	for fullKey := range s.objects {
		if strings.HasPrefix(fullKey, bucket+"/"+prefix) {
			keys = append(keys, strings.TrimPrefix(fullKey, bucket+"/"))
		}
	}
	return keys
}

// PresignedURL returns a fake presigned URL (not network-accessible).
func (s *MockObjectStore) PresignedURL(_ context.Context, bucket, key string, _ time.Duration) (string, error) {
	return fmt.Sprintf("https://mock-store.test/%s/%s?token=mock", bucket, key), nil
}

// Reset clears all stored objects.
func (s *MockObjectStore) Reset() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.objects = make(map[string]*ObjectMeta)
	s.CallLog = nil
}

// SentEmail captures a single outbound email for test assertions.
type SentEmail struct {
	To      string
	Subject string
	Body    string
	SentAt  time.Time
}

// MockEmailSender captures emails instead of delivering them.
type MockEmailSender struct {
	mu      sync.Mutex
	Sent    []*SentEmail
	CallLog []string
}

// NewMockEmailSender returns a fresh MockEmailSender.
func NewMockEmailSender() *MockEmailSender {
	return &MockEmailSender{}
}

func (e *MockEmailSender) Send(_ context.Context, to, subject, body string) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.Sent = append(e.Sent, &SentEmail{To: to, Subject: subject, Body: body, SentAt: time.Now()})
	e.CallLog = append(e.CallLog, fmt.Sprintf("SEND to=%s subject=%q", to, subject))
	return nil
}

// LastEmailTo returns the most recent email sent to the given address, or nil.
func (e *MockEmailSender) LastEmailTo(to string) *SentEmail {
	e.mu.Lock()
	defer e.mu.Unlock()
	for i := len(e.Sent) - 1; i >= 0; i-- {
		if e.Sent[i].To == to {
			return e.Sent[i]
		}
	}
	return nil
}

// Reset clears all captured emails.
func (e *MockEmailSender) Reset() {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.Sent = nil
	e.CallLog = nil
}

// FullServiceMocks bundles all mocks for services that need everything.
type FullServiceMocks struct {
	LLM      *MockLLMProvider
	Redis    *MockRedisClient
	Temporal *MockTemporalClient
	Store    *MockObjectStore
	Email    *MockEmailSender
}

// NewFullServiceMocks returns a fresh bundle of all mocks.
func NewFullServiceMocks() *FullServiceMocks {
	return &FullServiceMocks{
		LLM:      NewMockLLMProvider(),
		Redis:    NewMockRedisClient(),
		Temporal: NewMockTemporalClient(),
		Store:    NewMockObjectStore(),
		Email:    NewMockEmailSender(),
	}
}

// Reset resets all mocks between tests.
func (m *FullServiceMocks) Reset() {
	m.LLM.Reset()
	m.Redis.Reset()
	m.Temporal.Reset()
	m.Store.Reset()
	m.Email.Reset()
}
