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

	thumbnailv1 "github.com/autoniix/autoniix/gen/go/autoniix/thumbnail/v1"
	thumbnail "github.com/autoniix/autoniix/services/service-thumbnail"
	"github.com/autoniix/autoniix/libs/go/shared/httpx"
	sharedlog "github.com/autoniix/autoniix/libs/go/shared/log"
	"github.com/kelseyhightower/envconfig"
	"google.golang.org/grpc"
)

type Config struct {
	GRPCPort         int    `envconfig:"GRPC_PORT"          default:"9004"`
	HTTPPort         int    `envconfig:"HTTP_PORT"          default:"8095"`
	PythonThumbnailURL string `envconfig:"PYTHON_THUMBNAIL_URL" default:"http://thumbnail:8005"`
}

func main() {
	var cfg Config
	if err := envconfig.Process("", &cfg); err != nil {
		fmt.Fprintf(os.Stderr, "config error: %v\n", err)
		os.Exit(1)
	}
	logger := sharedlog.New("service-thumbnail")
	defer logger.Sync() //nolint:errcheck

	grpcSrv := grpc.NewServer()
	thumbnailv1.RegisterThumbnailServiceServer(grpcSrv, thumbnail.NewServer(cfg.PythonThumbnailURL, logger))

	grpcLn, err := net.Listen("tcp", fmt.Sprintf(":%d", cfg.GRPCPort))
	if err != nil {
		logger.Fatalw("thumbnail.listen_failed", "error", err)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		logger.Infow("thumbnail.grpc_listening", "port", cfg.GRPCPort)
		if err := grpcSrv.Serve(grpcLn); err != nil {
			logger.Errorw("thumbnail.grpc_error", "error", err)
		}
	}()

	router := httpx.NewRouter()
	httpSrv := &http.Server{Addr: fmt.Sprintf(":%d", cfg.HTTPPort), Handler: router}
	go func() {
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Errorw("thumbnail.http_error", "error", err)
		}
	}()

	<-ctx.Done()
	grpcSrv.GracefulStop()
	shutCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	httpSrv.Shutdown(shutCtx) //nolint:errcheck
}
