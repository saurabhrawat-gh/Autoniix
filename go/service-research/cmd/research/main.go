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

	researchv1 "github.com/autoniix/autoniix/gen/go/autoniix/research/v1"
	"github.com/autoniix/autoniix/go/service-research"
	"github.com/autoniix/autoniix/go/shared/httpx"
	sharedlog "github.com/autoniix/autoniix/go/shared/log"
	"github.com/kelseyhightower/envconfig"
	"google.golang.org/grpc"
)

type Config struct {
	GRPCPort          int    `envconfig:"GRPC_PORT"           default:"9006"`
	HTTPPort          int    `envconfig:"HTTP_PORT"           default:"8094"`
	PythonResearchURL string `envconfig:"PYTHON_RESEARCH_URL" default:"http://research:8006"`
}

func main() {
	var cfg Config
	if err := envconfig.Process("", &cfg); err != nil {
		fmt.Fprintf(os.Stderr, "config error: %v\n", err)
		os.Exit(1)
	}
	logger := sharedlog.New("service-research")
	defer logger.Sync() //nolint:errcheck

	grpcSrv := grpc.NewServer()
	researchv1.RegisterResearchServiceServer(grpcSrv, research.NewServer(cfg.PythonResearchURL, logger))

	grpcLn, err := net.Listen("tcp", fmt.Sprintf(":%d", cfg.GRPCPort))
	if err != nil {
		logger.Fatalw("research.listen_failed", "error", err)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		logger.Infow("research.grpc_listening", "port", cfg.GRPCPort)
		if err := grpcSrv.Serve(grpcLn); err != nil {
			logger.Errorw("research.grpc_error", "error", err)
		}
	}()

	router := httpx.NewRouter()
	httpSrv := &http.Server{Addr: fmt.Sprintf(":%d", cfg.HTTPPort), Handler: router}
	go func() {
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Errorw("research.http_error", "error", err)
		}
	}()

	<-ctx.Done()
	grpcSrv.GracefulStop()
	shutCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	httpSrv.Shutdown(shutCtx) //nolint:errcheck
}
