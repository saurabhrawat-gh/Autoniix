// Package proxy provides a generic HTTP proxy helper used by Go gRPC services
// that delegate ML-heavy work to Python microservices.
package proxy

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// Client is a thin JSON-over-HTTP client for proxying gRPC calls to Python services.
type Client struct {
	baseURL    string
	httpClient *http.Client
}

// New creates a proxy Client targeting pythonURL.
func New(pythonURL string) *Client {
	return &Client{
		baseURL:    strings.TrimRight(pythonURL, "/"),
		httpClient: &http.Client{Timeout: 120 * time.Second},
	}
}

// Post sends a JSON POST to path and returns the decoded response body.
// Returns an empty map when pythonURL is not configured.
func (c *Client) Post(ctx context.Context, path string, payload interface{}) (map[string]interface{}, error) {
	if c.baseURL == "" {
		return map[string]interface{}{}, nil
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+path, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("upstream %d: %s", resp.StatusCode, string(respBody))
	}
	var result map[string]interface{}
	_ = json.Unmarshal(respBody, &result)
	return result, nil
}

// StrField extracts a string field from a decoded map (handles nested "data" key).
func StrField(m map[string]interface{}, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	if data, ok := m["data"].(map[string]interface{}); ok {
		if v, ok := data[key].(string); ok {
			return v
		}
	}
	return ""
}

// FloatField extracts a float64 field from a decoded map.
func FloatField(m map[string]interface{}, key string) float64 {
	if v, ok := m[key].(float64); ok {
		return v
	}
	if data, ok := m["data"].(map[string]interface{}); ok {
		if v, ok := data[key].(float64); ok {
			return v
		}
	}
	return 0
}
