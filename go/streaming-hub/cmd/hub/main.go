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

	streamingv1 "github.com/autoniix/autoniix/gen/go/autoniix/streaming/v1"
	"github.com/autoniix/autoniix/go/shared/httpx"
	sharedlog "github.com/autoniix/autoniix/go/shared/log"
	streaminghub "github.com/autoniix/autoniix/go/streaming-hub"
	"github.com/kelseyhightower/envconfig"
	"github.com/redis/go-redis/v9"
	"google.golang.org/grpc"
)

type Config struct {
	GRPCPort int    `envconfig:"GRPC_PORT" default:"9002"`
	HTTPPort int    `envconfig:"HTTP_PORT" default:"8092"`
	RedisURL string `envconfig:"REDIS_URL" default:"redis://redis:6379"`
}

func main() {
	var cfg Config
	if err := envconfig.Process("", &cfg); err != nil {
		fmt.Fprintf(os.Stderr, "config error: %v\n", err)
		os.Exit(1)
	}

	logger := sharedlog.New("streaming-hub")
	defer logger.Sync() //nolint:errcheck

	// Optional Redis (graceful no-op if unavailable).
	var rdb *redis.Client
	opt, err := redis.ParseURL(cfg.RedisURL)
	if err != nil {
		logger.Warnw("streaming.redis_parse_failed", "error", err)
	} else {
		rdb = redis.NewClient(opt)
		pingCtx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		if pingErr := rdb.Ping(pingCtx).Err(); pingErr != nil {
			logger.Warnw("streaming.redis_unavailable", "error", pingErr)
			rdb = nil
		}
		cancel()
	}

	hub := streaminghub.NewHub(rdb, logger)
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	hub.StartRedisConsumer(ctx)

	// gRPC server.
	grpcSrv := grpc.NewServer()
	streamingv1.RegisterEventStreamServiceServer(grpcSrv, streaminghub.NewServer(hub, logger))

	grpcLn, listenErr := net.Listen("tcp", fmt.Sprintf(":%d", cfg.GRPCPort))
	if listenErr != nil {
		logger.Fatalw("streaming.grpc_listen_failed", "error", listenErr)
	}
	go func() {
		logger.Infow("streaming.grpc_listening", "port", cfg.GRPCPort)
		if serveErr := grpcSrv.Serve(grpcLn); serveErr != nil {
			logger.Errorw("streaming.grpc_serve_error", "error", serveErr)
		}
	}()

	// HTTP health server.
	router := httpx.NewRouter()
	httpSrv := &http.Server{Addr: fmt.Sprintf(":%d", cfg.HTTPPort), Handler: router}
	go func() {
		logger.Infow("streaming.http_listening", "port", cfg.HTTPPort)
		if serveErr := httpSrv.ListenAndServe(); serveErr != nil && serveErr != http.ErrServerClosed {
			logger.Errorw("streaming.http_serve_error", "error", serveErr)
		}
	}()

	<-ctx.Done()
	logger.Info("streaming.shutting_down")
	grpcSrv.GracefulStop()
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	httpSrv.Shutdown(shutdownCtx) //nolint:errcheck
}
