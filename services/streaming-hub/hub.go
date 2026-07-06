package streaminghub

import (
	"context"
	"encoding/json"
	"sync"
	"time"

	streamingv1 "github.com/autoniix/autoniix/gen/go/autoniix/streaming/v1"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
	"google.golang.org/protobuf/types/known/timestamppb"
)

const redisChannel = "autoniix:events"

// subscriber holds a single active Subscribe RPC.
type subscriber struct {
	id          string
	workspaceID string
	eventTypes  map[string]struct{}
	ch          chan *streamingv1.Event
}

// Hub manages pub/sub between Publish callers and Subscribe streams.
type Hub struct {
	mu   sync.RWMutex
	subs map[string]*subscriber
	rdb  *redis.Client
	log  *zap.SugaredLogger
}

func NewHub(rdb *redis.Client, log *zap.SugaredLogger) *Hub {
	return &Hub{
		subs: make(map[string]*subscriber),
		rdb:  rdb,
		log:  log,
	}
}

// Subscribe registers a subscriber and returns a channel that receives matching events.
// The caller must call Unsubscribe(id) when done.
func (h *Hub) Subscribe(req *streamingv1.SubscribeRequest) (string, <-chan *streamingv1.Event) {
	s := &subscriber{
		id:          uuid.NewString(),
		workspaceID: req.WorkspaceId,
		eventTypes:  make(map[string]struct{}),
		ch:          make(chan *streamingv1.Event, 64),
	}
	for _, t := range req.EventTypes {
		s.eventTypes[t] = struct{}{}
	}
	h.mu.Lock()
	h.subs[s.id] = s
	h.mu.Unlock()
	return s.id, s.ch
}

// Unsubscribe removes a subscriber by id and closes its channel.
func (h *Hub) Unsubscribe(id string) {
	h.mu.Lock()
	s, ok := h.subs[id]
	if ok {
		delete(h.subs, id)
	}
	h.mu.Unlock()
	if ok {
		close(s.ch)
	}
}

// Publish fans an event out to all matching subscribers and pushes to Redis.
func (h *Hub) Publish(ctx context.Context, event *streamingv1.Event) error {
	if event.Id == "" {
		event.Id = uuid.NewString()
	}
	if event.Timestamp == nil {
		event.Timestamp = timestamppb.New(time.Now().UTC())
	}

	data, err := json.Marshal(eventToMap(event))
	if err != nil {
		return err
	}
	if h.rdb != nil {
		if err := h.rdb.Publish(ctx, redisChannel, data).Err(); err != nil {
			h.log.Warnw("streaming.redis_publish_failed", "error", err)
		}
	}

	h.fanout(event)
	return nil
}

func (h *Hub) fanout(event *streamingv1.Event) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	for _, s := range h.subs {
		if s.workspaceID != "" && s.workspaceID != event.WorkspaceId {
			continue
		}
		if len(s.eventTypes) > 0 {
			if _, ok := s.eventTypes[event.Type]; !ok {
				continue
			}
		}
		select {
		case s.ch <- event:
		default:
			// slow consumer — drop
		}
	}
}

// StartRedisConsumer starts a goroutine that reads from the Redis pub/sub channel
// and fans events out to local subscribers (multi-instance support).
func (h *Hub) StartRedisConsumer(ctx context.Context) {
	if h.rdb == nil {
		return
	}
	go func() {
		sub := h.rdb.Subscribe(ctx, redisChannel)
		defer sub.Close()
		for {
			msg, err := sub.ReceiveMessage(ctx)
			if err != nil {
				if ctx.Err() != nil {
					return
				}
				h.log.Warnw("streaming.redis_receive_failed", "error", err)
				time.Sleep(time.Second)
				continue
			}
			var raw map[string]interface{}
			if err := json.Unmarshal([]byte(msg.Payload), &raw); err != nil {
				continue
			}
			event := mapToEvent(raw)
			h.fanout(event)
		}
	}()
}

func eventToMap(e *streamingv1.Event) map[string]interface{} {
	m := map[string]interface{}{
		"id":           e.Id,
		"type":         e.Type,
		"workspace_id": e.WorkspaceId,
	}
	if e.Timestamp != nil {
		m["ts"] = e.Timestamp.AsTime().UnixMilli()
	}
	return m
}

func mapToEvent(m map[string]interface{}) *streamingv1.Event {
	e := &streamingv1.Event{}
	if v, ok := m["id"].(string); ok {
		e.Id = v
	}
	if v, ok := m["type"].(string); ok {
		e.Type = v
	}
	if v, ok := m["workspace_id"].(string); ok {
		e.WorkspaceId = v
	}
	return e
}
