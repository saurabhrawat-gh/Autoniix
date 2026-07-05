package script

import (
	"context"

	commonv1 "github.com/autoniix/autoniix/gen/go/autoniix/common/v1"
	scriptv1 "github.com/autoniix/autoniix/gen/go/autoniix/script/v1"
	"github.com/autoniix/autoniix/go/shared/proxy"
	"go.uber.org/zap"
)

// Server proxies script generation to the Python script microservice.
type Server struct {
	scriptv1.UnimplementedScriptServiceServer
	client *proxy.Client
	log    *zap.SugaredLogger
}

func NewServer(pythonURL string, log *zap.SugaredLogger) *Server {
	return &Server{client: proxy.New(pythonURL), log: log}
}

func (s *Server) GenerateScript(ctx context.Context, req *scriptv1.GenerateScriptRequest) (*scriptv1.GenerateScriptResponse, error) {
	payload := map[string]interface{}{
		"channel_id":   req.ChannelId,
		"content_mode": "short",
		"topic":        req.Topic,
		"niche":        req.Niche,
	}
	resp, err := s.client.Post(ctx, "/generate", payload)
	if err != nil {
		s.log.Warnw("script.generate_failed", "error", err)
		return &scriptv1.GenerateScriptResponse{}, nil
	}

	data, _ := resp["data"].(map[string]interface{})
	if data == nil {
		data = resp
	}

	sc := &scriptv1.Script{
		Topic:   req.Topic,
		Content: proxy.StrField(data, "script"),
	}
	cost := proxy.FloatField(resp, "cost_usd")
	return &scriptv1.GenerateScriptResponse{Script: sc, GenerationCost: cost}, nil
}

func (s *Server) ValidateScript(ctx context.Context, req *scriptv1.ValidateScriptRequest) (*scriptv1.ValidateScriptResponse, error) {
	payload := map[string]interface{}{
		"content_id": req.ScriptId,
		"script":     req.Content,
	}
	resp, err := s.client.Post(ctx, "/analyze", payload)
	if err != nil {
		return &scriptv1.ValidateScriptResponse{Valid: true}, nil
	}
	score := proxy.FloatField(resp, "score")
	if score == 0 {
		if data, ok := resp["data"].(map[string]interface{}); ok {
			score = proxy.FloatField(data, "retention_score")
		}
	}
	return &scriptv1.ValidateScriptResponse{Valid: true, QualityScore: score}, nil
}

func (s *Server) ExpandScript(ctx context.Context, req *scriptv1.ExpandScriptRequest) (*scriptv1.ExpandScriptResponse, error) {
	payload := map[string]interface{}{
		"script_id":  req.ScriptId,
		"outline":    req.Outline,
		"channel_id": req.ChannelId,
	}
	resp, err := s.client.Post(ctx, "/expand", payload)
	if err != nil {
		return &scriptv1.ExpandScriptResponse{}, nil
	}
	data, _ := resp["data"].(map[string]interface{})
	if data == nil {
		data = resp
	}
	sc := &scriptv1.Script{Content: proxy.StrField(data, "script")}
	return &scriptv1.ExpandScriptResponse{Script: sc}, nil
}

func (s *Server) GetScriptHistory(ctx context.Context, req *scriptv1.GetScriptHistoryRequest) (*scriptv1.GetScriptHistoryResponse, error) {
	return &scriptv1.GetScriptHistoryResponse{
		Pagination: &commonv1.PaginationResponse{},
	}, nil
}
