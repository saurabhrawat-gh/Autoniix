// Package httpx contains HTTP helpers shared by Go services:
// a chi router preset, health/readiness handlers, and standard middleware.
package httpx

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

// NewRouter returns a chi router preloaded with request-id, real-ip,
// recovery, and a 30-second timeout. Services add their own handlers.
func NewRouter() *chi.Mux {
	r := chi.NewRouter()
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Recoverer)
	r.Use(middleware.Timeout(30 * time.Second))
	return r
}

// Health returns a handler that always reports 200 with a JSON status
// body. Suitable for /health liveness probes.
func Health(service string) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{
			"status":  "ok",
			"service": service,
		})
	}
}

// Ready returns a handler that runs the provided check and reports 200
// if it returns nil, 503 otherwise. Suitable for /ready readiness probes.
func Ready(check func() error) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		if err := check(); err != nil {
			writeJSON(w, http.StatusServiceUnavailable, map[string]string{
				"status": "not_ready",
				"error":  err.Error(),
			})
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "ready"})
	}
}

func writeJSON(w http.ResponseWriter, code int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(body)
}
