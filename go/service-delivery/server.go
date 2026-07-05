package delivery

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	deliveryv1 "github.com/autoniix/autoniix/gen/go/autoniix/delivery/v1"
	"go.uber.org/zap"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// Server implements DeliveryServiceServer.
// YouTube upload is delegated to the Python delivery service via HTTP proxy
// while SEO scoring is handled natively in Go.
type Server struct {
	deliveryv1.UnimplementedDeliveryServiceServer
	pythonURL  string
	httpClient *http.Client
	log        *zap.SugaredLogger
}

func NewServer(pythonDeliveryURL string, log *zap.SugaredLogger) *Server {
	return &Server{
		pythonURL:  strings.TrimRight(pythonDeliveryURL, "/"),
		httpClient: &http.Client{Timeout: 120 * time.Second},
		log:        log,
	}
}

// GetSEOScore is handled natively in Go.
func (s *Server) GetSEOScore(_ context.Context, req *deliveryv1.GetSEOScoreRequest) (*deliveryv1.GetSEOScoreResponse, error) {
	seo := ScoreTitleSEO(req.Title)
	tags := SuggestTags(req.Title, req.Niche, req.Tags)
	return &deliveryv1.GetSEOScoreResponse{
		SeoScore:      seo.Score,
		Factors:       seo.Factors,
		SuggestedTags: tags,
	}, nil
}

// UploadVideo proxies to the Python delivery service.
func (s *Server) UploadVideo(ctx context.Context, req *deliveryv1.UploadVideoRequest) (*deliveryv1.UploadVideoResponse, error) {
	payload := map[string]interface{}{
		"content_id":                    req.ContentId,
		"channel_id":                    req.ChannelId,
		"content_mode":                  req.ContentMode,
		"title":                         req.Title,
		"description":                   req.Description,
		"tags":                          req.Tags,
		"video_url":                     req.VideoUrl,
		"thumbnail_url":                 req.ThumbnailUrl,
		"privacy_status":                req.PrivacyStatus,
		"category_id":                   req.CategoryId,
		"is_short":                      req.IsShort,
		"quality_scores":                req.QualityScores,
		"quality_gate_override":         req.QualityGateOverride,
		"quality_gate_override_reason":  req.QualityGateOverrideReason,
		"quality_gate_override_by":      req.QualityGateOverrideBy,
	}

	resp, err := s.postToPython(ctx, "/upload", payload)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "python delivery /upload: %v", err)
	}
	data, _ := resp["data"].(map[string]interface{})
	return &deliveryv1.UploadVideoResponse{
		YoutubeVideoId: strVal(data, "youtube_video_id"),
		YoutubeUrl:     strVal(data, "youtube_url"),
		PrivacyStatus:  strVal(data, "privacy_status"),
	}, nil
}

// ComputeMetadata runs Go-native SEO then proxies DB write to Python.
func (s *Server) ComputeMetadata(ctx context.Context, req *deliveryv1.ComputeMetadataRequest) (*deliveryv1.ComputeMetadataResponse, error) {
	seo := ScoreTitleSEO(req.Title)
	tags := SuggestTags(req.Title, req.Niche, req.Tags)

	payload := map[string]interface{}{
		"content_id":     req.ContentId,
		"channel_id":     req.ChannelId,
		"content_mode":   req.ContentMode,
		"title":          req.Title,
		"description":    req.Description,
		"tags":           tags,
		"niche":          req.Niche,
		"quality_scores": req.QualityScores,
		"is_short":       req.IsShort,
	}
	resp, err := s.postToPython(ctx, "/compute-metadata", payload)
	if err != nil {
		s.log.Warnw("delivery.compute_metadata_python_failed", "error", err)
	}

	var catID string
	var hashtags []string
	var finalScore float64 = seo.Score
	if data, ok := resp["data"].(map[string]interface{}); ok {
		catID = strVal(data, "category_id")
		finalScore = floatVal(data, "final_composite_score")
		if ht, ok := data["hashtags"].([]interface{}); ok {
			for _, h := range ht {
				if s, ok := h.(string); ok {
					hashtags = append(hashtags, s)
				}
			}
		}
	}

	return &deliveryv1.ComputeMetadataResponse{
		Title:               req.Title,
		Description:         req.Description,
		Tags:                tags,
		Hashtags:            hashtags,
		CategoryId:          catID,
		SeoScore:            seo.Score,
		FinalCompositeScore: finalScore,
	}, nil
}

// HumanReview proxies to the Python delivery service.
func (s *Server) HumanReview(ctx context.Context, req *deliveryv1.HumanReviewRequest) (*deliveryv1.HumanReviewResponse, error) {
	payload := map[string]interface{}{
		"content_id": req.ContentId,
		"approved":   req.Approved,
		"reviewer":   req.Reviewer,
		"notes":      req.Notes,
	}
	resp, err := s.postToPython(ctx, "/human-review", payload)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "python delivery /human-review: %v", err)
	}
	ok := strVal(resp, "status") == "success"
	return &deliveryv1.HumanReviewResponse{Success: ok, Message: strVal(resp, "detail")}, nil
}

func (s *Server) postToPython(ctx context.Context, path string, payload interface{}) (map[string]interface{}, error) {
	if s.pythonURL == "" {
		return map[string]interface{}{}, nil
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.pythonURL+path, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	httpResp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer httpResp.Body.Close()
	respBody, _ := io.ReadAll(httpResp.Body)
	if httpResp.StatusCode >= 400 {
		return nil, fmt.Errorf("python returned %d: %s", httpResp.StatusCode, string(respBody))
	}
	var result map[string]interface{}
	_ = json.Unmarshal(respBody, &result)
	return result, nil
}

func strVal(m map[string]interface{}, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

func floatVal(m map[string]interface{}, key string) float64 {
	if v, ok := m[key].(float64); ok {
		return v
	}
	return 0
}
