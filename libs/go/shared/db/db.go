// Package db provides a shared pgxpool constructor with sane defaults.
//
// All Go services connect through this package so pool sizing, health
// checks, and connection lifecycle are consistent.
package db

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Config describes how a service connects to Postgres.
type Config struct {
	// URL is a standard postgres:// connection string.
	URL string
	// MinConns is the minimum size of the connection pool.
	MinConns int32
	// MaxConns is the maximum size of the connection pool.
	MaxConns int32
	// ConnectTimeout bounds the initial dial.
	ConnectTimeout time.Duration
}

// DefaultConfig returns pool settings suitable for a low-throughput
// worker (dispatcher, streaming hub). Services with heavier RPS should
// override MinConns/MaxConns explicitly.
func DefaultConfig(url string) Config {
	return Config{
		URL:            url,
		MinConns:       1,
		MaxConns:       10,
		ConnectTimeout: 10 * time.Second,
	}
}

// Open returns a pgxpool.Pool that has already passed a ping check.
// The returned pool is safe for concurrent use; caller owns Close.
func Open(ctx context.Context, cfg Config) (*pgxpool.Pool, error) {
	if cfg.URL == "" {
		return nil, fmt.Errorf("db: empty DATABASE_URL")
	}
	pcfg, err := pgxpool.ParseConfig(cfg.URL)
	if err != nil {
		return nil, fmt.Errorf("db: parse url: %w", err)
	}
	if cfg.MinConns > 0 {
		pcfg.MinConns = cfg.MinConns
	}
	if cfg.MaxConns > 0 {
		pcfg.MaxConns = cfg.MaxConns
	}

	dialCtx, cancel := context.WithTimeout(ctx, cfg.ConnectTimeout)
	defer cancel()

	pool, err := pgxpool.NewWithConfig(dialCtx, pcfg)
	if err != nil {
		return nil, fmt.Errorf("db: dial: %w", err)
	}
	if err := pool.Ping(dialCtx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("db: ping: %w", err)
	}
	return pool, nil
}
