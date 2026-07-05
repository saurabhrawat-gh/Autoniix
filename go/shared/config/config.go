// Package config centralizes env-driven configuration for Go services.
//
// Services declare a struct with `envconfig:"..."` tags and call
// config.MustLoad(prefix, &cfg) at startup. Failure to parse is fatal
// — services should NEVER start with half-initialized config.
package config

import (
	"fmt"

	"github.com/kelseyhightower/envconfig"
)

// MustLoad parses env vars into cfg under the given prefix. Panics on error;
// intended to be called at process startup.
func MustLoad(prefix string, cfg any) {
	if err := envconfig.Process(prefix, cfg); err != nil {
		panic(fmt.Sprintf("config: failed to load %q: %v", prefix, err))
	}
}
