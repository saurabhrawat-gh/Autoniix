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

	deliveryv1 "github.com/autoniix/autoniix/gen/go/autoniix/delivery/v1"
	"github.com/autoniix/autoniix/services/service-delivery"
	"github.com/autoniix/autoniix/libs/go/shared/httpx"
	sharedlog "github.com/autoniix/autoniix/libs/go/shared/log"
	"github.com/kelseyhightower/envconfig"
	"google.golang.org/grpc"
)

type Config struct {
	GRPCPort          int    `envconfig:"GRPC_PORT"           default:"9003"`
	HTTPPort          int    `envconfig:"HTTP_PORT"           default:"8097"`
	PythonDeliveryURL string `envconfig:"PYTHON_DELIVERY_URL" default:"http://delivery:8007"`
}

func main() {
	var cfg Config
	if err := envconfig.Process("", &cfg); err != nil {
		fmt.Fprintf(os.Stderr, "config error: %v\n", err)
		os.Exit(1)
	}

	logger := sharedlog.New("service-delivery")
	defer logger.Sync() //nolint:errcheck

	srv := delivery.NewServer(cfg.PythonDeliveryURL, logger)

	grpcSrv := grpc.NewServer()
	deliveryv1.RegisterDeliveryServiceServer(grpcSrv, srv)

	grpcLn, err := net.Listen("tcp", fmt.Sprintf(":%d", cfg.GRPCPort))
	if err != nil {
		logger.Fatalw("delivery.grpc_listen_failed", "error", err)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		logger.Infow("delivery.grpc_listening", "port", cfg.GRPCPort)
		if err := grpcSrv.Serve(grpcLn); err != nil {
			logger.Errorw("delivery.grpc_serve_error", "error", err)
		}
	}()

	router := httpx.NewRouter()
	httpSrv := &http.Server{Addr: fmt.Sprintf(":%d", cfg.HTTPPort), Handler: router}
	go func() {
		logger.Infow("delivery.http_listening", "port", cfg.HTTPPort)
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Errorw("delivery.http_serve_error", "error", err)
		}
	}()

	<-ctx.Done()
	logger.Info("delivery.shutting_down")
	grpcSrv.GracefulStop()
	shutCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	httpSrv.Shutdown(shutCtx) //nolint:errcheck
}
