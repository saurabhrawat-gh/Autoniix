package main

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	voicev1 "github.com/autoniix/autoniix/gen/go/autoniix/voice/v1"
	"github.com/autoniix/autoniix/s# Rewrite all Go imports across the repo
find . -typutfind . -typutfind . -typutfind . -typutiix/autoniix/services/streaming-hub"
	"github.com/autoniix/autoniix/libs/go/shared/httpx"
	sharedlog "github.com/autoniix/autoniix/libs/go/shared/log"
	"github.com/kelseyhightower/envconfig"
	"google.golang.org/grpc"
)

type Config struct {
	GRPCPort       int    `envconfig:"GRPC_PORT"        default:"9005"`
	HTTPPort       int    `envconfig:"HTTP_PORT"        default:"8093"`
	PythonVoiceURL string `envconfig:"PYTHON_VOICE_URL" default:"http://voice:8003"`
}

func main() {
	var cfg Config
	if err := envconfig.Process("", &cfg); err != nil {
		fmt.Fprintf(os.Stderr, "config error: %v\n", err)
		os.Exit(1)
	}
	logger := sharedlog.New("service-voice")
	defer logger.Sync() //nolint:errcheck

	grpcSrv := grpc.NewServer()
	voicev1.RegisterVoiceServiceServer(grpcSrv, voice.NewServer(cfg.PythonVoiceURL, logger))

	grpcLn, err := net.Listen("tcp", fmt.Sprintf(":%d", cfg.GRPCPort))
	if err != nil {
		logger.Fatalw("voice.listen_failed", "error", err)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		logger.Infow("voice.grpc_listening", "port", cfg.GRPCPort)
		if err := grpcSrv.Serve(grpcLn); err != nil {
			logger.Errorw("voice.grpc_error", "error", err)
		}
	}()

	router := httpx.NewRouter()
	httpSrv := &http.Server{Addr: fmt.Sprintf(":%d", cfg.HTTPPort), Handler: router}
	go func() {
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Errorw("voice.http_error", "error", err)
		}
	}()

	<-ctx.Done()
	grpcSrv.GracefulStop()
	shutCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	httpSrv.Shutdown(shutCtx) //nolint:errcheck
}
