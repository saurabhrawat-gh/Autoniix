package voice

import (
	"context"

	voicev1 "github.com/autoniix/autoniix/gen/go/autoniix/voice/v1"
	"github.com/autoniix/autoniix/go/shared/proxy"
	"go.uber.org/zap"
)

// Server proxies voice synthesis requests to the Python voice microservice.
type Server struct {
	voicev1.UnimplementedVoiceServiceServer
	client *proxy.Client
	log    *zap.SugaredLogger
}

func NewServer(pythonURL string, log *zap.SugaredLogger) *Server {
	return &Server{client: proxy.New(pythonURL), log: log}
}

func (s *Server) SynthesizeVoice(ctx context.Context, req *voicev1.SynthesizeVoiceRequest) (*voicev1.SynthesizeVoiceResponse, error) {
	var settings map[string]interface{}
	if req.Settings != nil {
		settings = map[string]interface{}{
			"speed":            req.Settings.Speed,
			"pitch":            req.Settings.Pitch,
			"stability":        req.Settings.Stability,
			"similarity_boost": req.Settings.SimilarityBoost,
			"style":            req.Settings.Style,
		}
	}
	payload := map[string]interface{}{
		"script_id":      req.ScriptId,
		"text":           req.Text,
		"voice_model_id": req.VoiceModelId,
		"channel_id":     req.ChannelId,
		"settings":       settings,
	}
	resp, err := s.client.Post(ctx, "/synthesize", payload)
	if err != nil {
		s.log.Warnw("voice.synthesize_failed", "error", err)
		return &voicev1.SynthesizeVoiceResponse{}, nil
	}
	data, _ := resp["data"].(map[string]interface{})
	if data == nil {
		data = resp
	}
	return &voicev1.SynthesizeVoiceResponse{
		AudioId:        proxy.StrField(data, "audio_id"),
		AudioUrl:       proxy.StrField(data, "audio_url"),
		GenerationCost: proxy.FloatField(data, "cost_usd"),
	}, nil
}

func (s *Server) ListVoiceModels(ctx context.Context, req *voicev1.ListVoiceModelsRequest) (*voicev1.ListVoiceModelsResponse, error) {
	resp, err := s.client.Post(ctx, "/list-models", map[string]interface{}{
		"provider": req.Provider,
		"language": req.Language,
	})
	if err != nil {
		return &voicev1.ListVoiceModelsResponse{}, nil
	}
	var models []*voicev1.VoiceModel
	if data, ok := resp["data"].([]interface{}); ok {
		for _, item := range data {
			if m, ok := item.(map[string]interface{}); ok {
				models = append(models, &voicev1.VoiceModel{
					Id:       proxy.StrField(m, "id"),
					Name:     proxy.StrField(m, "name"),
					Provider: proxy.StrField(m, "provider"),
					Language: proxy.StrField(m, "language"),
				})
			}
		}
	}
	return &voicev1.ListVoiceModelsResponse{Models: models}, nil
}

func (s *Server) GetVoiceAudio(ctx context.Context, req *voicev1.GetVoiceAudioRequest) (*voicev1.GetVoiceAudioResponse, error) {
	resp, err := s.client.Post(ctx, "/get-audio", map[string]interface{}{"audio_id": req.AudioId})
	if err != nil {
		return &voicev1.GetVoiceAudioResponse{}, nil
	}
	return &voicev1.GetVoiceAudioResponse{
		Format: proxy.StrField(resp, "format"),
	}, nil
}
