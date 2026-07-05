package thumbnail

import (
	"context"

	thumbnailv1 "github.com/autoniix/autoniix/gen/go/autoniix/thumbnail/v1"
	commonv1 "github.com/autoniix/autoniix/gen/go/autoniix/common/v1"
	"github.com/autoniix/autoniix/go/shared/proxy"
	"go.uber.org/zap"
)

// Server proxies thumbnail generation to the Python thumbnail microservice.
type Server struct {
	thumbnailv1.UnimplementedThumbnailServiceServer
	client *proxy.Client
	log    *zap.SugaredLogger
}

func NewServer(pythonURL string, log *zap.SugaredLogger) *Server {
	return &Server{client: proxy.New(pythonURL), log: log}
}

func (s *Server) GenerateThumbnail(ctx context.Context, req *thumbnailv1.GenerateThumbnailRequest) (*thumbnailv1.GenerateThumbnailResponse, error) {
	payload := map[string]interface{}{
		"content_id":   req.ContentId,
		"channel_id":   req.ChannelId,
		"title":        req.Title,
		"niche":        req.Niche,
		"content_mode": req.ContentMode,
	}
	resp, err := s.client.Post(ctx, "/generate", payload)
	if err != nil {
		s.log.Warnw("thumbnail.generate_failed", "error", err)
		return &thumbnailv1.GenerateThumbnailResponse{}, nil
	}

	score := proxy.FloatField(resp, "thumbnail_score")
	ctr := proxy.FloatField(resp, "thumbnail_ctr_prediction")

	var selected *thumbnailv1.ThumbnailVariant
	if data, ok := resp["data"].(map[string]interface{}); ok {
		if st, ok := data["selected_thumbnail"].(map[string]interface{}); ok {
			selected = mapToVariant(st)
		}
	}

	return &thumbnailv1.GenerateThumbnailResponse{
		SelectedThumbnail:       selected,
		ThumbnailScore:          score,
		ThumbnailCtrPrediction:  ctr,
	}, nil
}

func (s *Server) GetThumbnailFeedback(ctx context.Context, req *thumbnailv1.ThumbnailFeedbackRequest) (*commonv1.Empty, error) {
	_, _ = s.client.Post(ctx, "/thumbnail-feedback", map[string]interface{}{
		"content_id": req.ContentId,
		"channel_id": req.ChannelId,
		"actual_ctr": req.ActualCtr,
		"impressions": req.Impressions,
	})
	return &commonv1.Empty{}, nil
}

func (s *Server) TrainModel(ctx context.Context, req *thumbnailv1.ThumbnailTrainRequest) (*thumbnailv1.ThumbnailTrainResponse, error) {
	resp, err := s.client.Post(ctx, "/thumbnail-train", map[string]interface{}{"niche": req.Niche})
	if err != nil {
		return &thumbnailv1.ThumbnailTrainResponse{Success: false, Message: err.Error()}, nil
	}
	return &thumbnailv1.ThumbnailTrainResponse{
		Success: proxy.StrField(resp, "status") == "success",
	}, nil
}

func mapToVariant(m map[string]interface{}) *thumbnailv1.ThumbnailVariant {
	v := &thumbnailv1.ThumbnailVariant{}
	if s, ok := m["url"].(string); ok {
		v.Url = s
	}
	if s, ok := m["concept_name"].(string); ok {
		v.ConceptName = s
	}
	if f, ok := m["thumbnail_score"].(float64); ok {
		v.ThumbnailScore = f
	}
	if f, ok := m["predicted_ctr"].(float64); ok {
		v.PredictedCtr = f
	}
	return v
}
