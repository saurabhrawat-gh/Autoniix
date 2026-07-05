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

	scriptv1 "github.com/autoniix/autoniix/gen/go/autoniix/script/v1"
	"github.com/autoniix/autoniix/go/service-script"
	"github.com/autoniix/autoniix/go/shared/httpx"
	sharedlog "github.com/autoniix/autoniix/go/shared/log"
	"github.com/kelseyhightower/envconfig"
	"google.golang.org/grpc"
)

type Config struct {
	GRPCPort        int    `envconfig:"GRPC_PORT"          default:"9007"`
	HTTPPort        int    `envconfig:"HTTP_PORT"          default:"8096"`
	PythonScriptURL string `envconfig:"PYTHON_SCRIPT_URL"  default:"http://script:8002"`
}

func main() {
	var cfg Config
	if err := envconfig.Process("", &cfg); err != nil {
		fmt.Fprintf(os.Stderr, "config error: %v\n", err)
		os.Exit(1)
	}
	logger := sharedlog.New("service-script")
	defer logger.Sync() //nolint:errcheck

	grpcSrv := grpc.NewServer()
	scriptv1.RegisterScriptServiceServer(grpcSrv, script.NewServer(cfg.PythonScriptURL, logger))

	grpcLn, err := net.Listen("tcp", fmt.Sprintf(":%d", cfg.GRPCPort))
	if err != nil {
		logger.Fatalw("script.listen_failed", "error", err)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		logger.Infow("script.grpc_listening", "port", cfg.GRPCPort)
		if err := grpcSrv.Serve(grpcLn); err != nil {
			logger.Errorw("script.grpc_error", "error", err)
		}
	}()

	router := httpx.NewRouter()
	httpSrv := &http.Server{Addr: fmt.Sprintf(":%d", cfg.HTTPPort), Handler: router}
	go func() {
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Errorw("script.http_error", "error", err)
		}
	}()

	<-ctx.Done()
	grpcSrv.GracefulStop()
	shutCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	httpSrv.Shutdown(shutCtx) //nolint:errcheck
}
