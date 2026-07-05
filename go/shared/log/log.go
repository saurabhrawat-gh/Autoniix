// Package log provides a shared structured logger for Go services.
//
// Convention: services call log.New(serviceName) at startup and thread
// the returned *zap.SugaredLogger through their handlers/workers.
package log

import (
	"os"
	"strings"

	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

// New returns a production-ready sugared logger tagged with the service name.
// The log level honors LOG_LEVEL (debug|info|warn|error). Default is info.
func New(service string) *zap.SugaredLogger {
	lvl := zapcore.InfoLevel
	switch strings.ToLower(os.Getenv("LOG_LEVEL")) {
	case "debug":
		lvl = zapcore.DebugLevel
	case "warn":
		lvl = zapcore.WarnLevel
	case "error":
		lvl = zapcore.ErrorLevel
	}
	cfg := zap.NewProductionConfig()
	cfg.Level = zap.NewAtomicLevelAt(lvl)
	cfg.EncoderConfig.TimeKey = "ts"
	cfg.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder
	cfg.InitialFields = map[string]any{"service": service}
	l, err := cfg.Build()
	if err != nil {
		// fall back to bare stderr logger — never panic on log init
		l = zap.NewExample()
	}
	return l.Sugar()
}
