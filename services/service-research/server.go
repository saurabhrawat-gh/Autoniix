package research

import (
	"context"

	commonv1 "github.com/autoniix/autoniix/gen/go/autoniix/common/v1"
	researchv1 "github.com/autoniix/autoniix/gen/go/autoniix/research/v1"
	"github.com/autoniix/autoniix/libs/go/shared/proxy"
	"go.uber.org/zap"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// Server proxies research requests to the Python research microservice.
type Server struct {
	researchv1.UnimplementedResearchServiceServer
	client *proxy.Client
	log    *zap.SugaredLogger
}

func NewServer(pythonURL string, log *zap.SugaredLogger) *Server {
	return &Server{client: proxy.New(pythonURL), log: log}
}

func (s *Server) DiscoverTopics(ctx context.Context, req *researchv1.DiscoverTopicsRequest) (*researchv1.DiscoverTopicsResponse, error) {
	payload := map[string]interface{}{
		"channel_id":        req.ChannelId,
		"content_mode":      "short",
		"topic_candidates":  []string{req.Niche},
	}
	resp, err := s.client.Post(ctx, "/research", payload)
	if err != nil {
		s.log.Warnw("research.discover_failed", "error", err)
		return &researchv1.DiscoverTopicsResponse{}, nil
	}

	var topics []*researchv1.Topic
	if data, ok := resp["data"].(map[string]interface{}); ok {
		if tList, ok := data["topics"].([]interface{}); ok {
			for _, item := range tList {
				if m, ok := item.(map[string]interface{}); ok {
					topics = append(topics, &researchv1.Topic{
						Text:  proxy.StrField(m, "text"),
						Score: proxy.FloatField(m, "score"),
					})
				}
			}
		}
	}
	return &researchv1.DiscoverTopicsResponse{Topics: topics}, nil
}

func (s *Server) CheckSimilarity(ctx context.Context, req *researchv1.CheckSimilarityRequest) (*researchv1.CheckSimilarityResponse, error) {
	payload := map[string]interface{}{
		"channel_id": req.ChannelId,
		"text":       req.Text,
		"text_type":  req.TextType,
		"top_k":      req.TopK,
	}
	resp, err := s.client.Post(ctx, "/check-similarity", payload)
	if err != nil {
		return &researchv1.CheckSimilarityResponse{}, nil
	}
	var matches []*researchv1.SimilarityMatch
	if data, ok := resp["data"].(map[string]interface{}); ok {
		if mList, ok := data["matches"].([]interface{}); ok {
			for _, item := range mList {
				if m, ok := item.(map[string]interface{}); ok {
					matches = append(matches, &researchv1.SimilarityMatch{
						Text:             proxy.StrField(m, "text"),
						CosineSimilarity: proxy.FloatField(m, "cosine_similarity"),
					})
				}
			}
		}
	}
	isDup := len(matches) > 0 && (len(matches) == 0 || proxy.FloatField(resp, "is_duplicate") > 0)
	return &researchv1.CheckSimilarityResponse{IsDuplicate: isDup, Matches: matches}, nil
}

func (s *Server) CalculateSaturation(ctx context.Context, req *researchv1.CalculateSaturationRequest) (*researchv1.CalculateSaturationResponse, error) {
	payload := map[string]interface{}{
		"topic": req.Topic,
		"niche": req.Niche,
	}
	resp, err := s.client.Post(ctx, "/saturation", payload)
	if err != nil {
		return &researchv1.CalculateSaturationResponse{}, nil
	}
	return &researchv1.CalculateSaturationResponse{
		SaturationScore: proxy.FloatField(resp, "saturation_score"),
	}, nil
}

func (s *Server) SelectTopic(ctx context.Context, req *researchv1.SelectTopicRequest) (*researchv1.SelectTopicResponse, error) {
	payload := map[string]interface{}{
		"channel_id":       req.ChannelId,
		"niche":            req.Niche,
		"candidate_topics": req.CandidateTopics,
	}
	resp, err := s.client.Post(ctx, "/select-topic", payload)
	if err != nil {
		return &researchv1.SelectTopicResponse{}, nil
	}
	data, _ := resp["data"].(map[string]interface{})
	if data == nil {
		data = resp
	}
	topic := &researchv1.Topic{Text: proxy.StrField(data, "selected_topic")}
	return &researchv1.SelectTopicResponse{
		SelectedTopic:   topic,
		SelectionReason: proxy.StrField(data, "selection_reason"),
	}, nil
}

func (s *Server) GetCompetitorInsights(ctx context.Context, req *researchv1.GetCompetitorInsightsRequest) (*researchv1.GetCompetitorInsightsResponse, error) {
	payload := map[string]interface{}{"niche": req.Niche, "limit": req.Limit}
	resp, err := s.client.Post(ctx, "/competitor-insights", payload)
	if err != nil {
		return &researchv1.GetCompetitorInsightsResponse{}, nil
	}
	_ = resp
	return &researchv1.GetCompetitorInsightsResponse{
		LastUpdated: timestamppb.Now(),
	}, nil
}

var _ = commonv1.Empty{}
