package streaminghub

import (
	"context"

	commonv1 "github.com/autoniix/autoniix/gen/go/autoniix/common/v1"
	streamingv1 "github.com/autoniix/autoniix/gen/go/autoniix/streaming/v1"
	"go.uber.org/zap"
)

var _ = zap.String // keep zap imported for SugaredLogger type reference

// Server implements streamingv1.EventStreamServiceServer.
type Server struct {
	streamingv1.UnimplementedEventStreamServiceServer
	hub *Hub
	log *zap.SugaredLogger
}

func NewServer(hub *Hub, log *zap.SugaredLogger) *Server {
	return &Server{hub: hub, log: log}
}

// Subscribe opens a server-streaming RPC that emits events to the caller.
func (s *Server) Subscribe(req *streamingv1.SubscribeRequest, stream streamingv1.EventStreamService_SubscribeServer) error {
	ctx := stream.Context()
	id, ch := s.hub.Subscribe(req)
	defer s.hub.Unsubscribe(id)

	s.log.Infow("streaming.subscribed",
		"subscriber_id", id,
		"workspace_id", req.WorkspaceId,
		"event_types", req.EventTypes,
	)

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case event, ok := <-ch:
			if !ok {
				return nil
			}
			if err := stream.Send(event); err != nil {
				s.log.Warnw("streaming.send_failed", "subscriber_id", id, "error", err)
				return err
			}
		}
	}
}

// Publish accepts an event and fans it out to all matching subscribers.
func (s *Server) Publish(ctx context.Context, req *streamingv1.PublishRequest) (*commonv1.Empty, error) {
	if req.Event == nil {
		return &commonv1.Empty{}, nil
	}
	if err := s.hub.Publish(ctx, req.Event); err != nil {
		s.log.Errorw("streaming.publish_failed", "error", err)
		return nil, err
	}
	return &commonv1.Empty{}, nil
}

// Acknowledge records that a subscriber processed an event (no-op for now).
func (s *Server) Acknowledge(_ context.Context, _ *streamingv1.AcknowledgeRequest) (*commonv1.Empty, error) {
	return &commonv1.Empty{}, nil
}
