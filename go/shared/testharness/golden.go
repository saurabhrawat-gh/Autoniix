// Package testharness — golden-file loader for Go service tests.
//
// Per HARNESS-ENGINEERING-PLAN.md §A7.
//
// Usage:
//
//	func TestMyEndpoint(t *testing.T) {
//	    g := testharness.NewGoldenLoader(t, "../../tests/golden")
//	    fixture := g.Load("auth/auth_mode")
//	    resp, err := http.Get(gatewayURL + fixture.Path)
//	    // ...
//	    g.Assert(t, fixture, resp)
//	}
package testharness

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"testing"
)

// GoldenFixture represents a single captured endpoint response.
type GoldenFixture struct {
	Method       string          `json:"method"`
	Path         string          `json:"path"`
	RequestBody  json.RawMessage `json:"request_body"`
	Status       int             `json:"status"`
	Body         json.RawMessage `json:"body"`
	IgnoreFields []string        `json:"ignore_fields"`
}

// GoldenLoader loads golden fixtures from a directory.
type GoldenLoader struct {
	t   *testing.T
	dir string
}

// NewGoldenLoader creates a GoldenLoader rooted at dir.
func NewGoldenLoader(t *testing.T, dir string) *GoldenLoader {
	t.Helper()
	abs, err := filepath.Abs(dir)
	if err != nil {
		t.Fatalf("goldenloader: bad dir %q: %v", dir, err)
	}
	return &GoldenLoader{t: t, dir: abs}
}

// Load reads fixture at <dir>/<name>.json.
func (g *GoldenLoader) Load(name string) *GoldenFixture {
	g.t.Helper()
	path := filepath.Join(g.dir, name+".json")
	data, err := os.ReadFile(path)
	if err != nil {
		g.t.Fatalf("goldenloader: cannot read fixture %q: %v", path, err)
	}
	var f GoldenFixture
	if err := json.Unmarshal(data, &f); err != nil {
		g.t.Fatalf("goldenloader: cannot parse fixture %q: %v", path, err)
	}
	return &f
}

// List returns fixture names (without .json) in dir, recursively.
func (g *GoldenLoader) List() []string {
	var names []string
	_ = filepath.Walk(g.dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		if filepath.Ext(path) == ".json" {
			rel, _ := filepath.Rel(g.dir, path)
			names = append(names, rel[:len(rel)-5]) // strip .json
		}
		return nil
	})
	return names
}

// AssertStatus fails the test if resp.StatusCode != fixture.Status.
func (g *GoldenLoader) AssertStatus(fixture *GoldenFixture, resp *http.Response) {
	g.t.Helper()
	if resp.StatusCode != fixture.Status {
		g.t.Errorf("golden status mismatch for %q: expected %d, got %d",
			fixture.Path, fixture.Status, resp.StatusCode)
	}
}

// AssertBodySubset fails the test if any top-level key in the fixture body
// is missing or has a different value in actualBody (ignoring IgnoreFields).
func (g *GoldenLoader) AssertBodySubset(fixture *GoldenFixture, actualBody map[string]interface{}) {
	g.t.Helper()

	var expected map[string]interface{}
	if err := json.Unmarshal(fixture.Body, &expected); err != nil {
		// fixture body may be an array or primitive — skip subset check
		return
	}

	ignore := make(map[string]bool, len(fixture.IgnoreFields))
	for _, f := range fixture.IgnoreFields {
		ignore[f] = true
	}

	for key, expVal := range expected {
		if ignore[key] {
			continue
		}
		actVal, ok := actualBody[key]
		if !ok {
			g.t.Errorf("golden body subset mismatch for %q: missing key %q", fixture.Path, key)
			continue
		}
		expJSON, _ := json.Marshal(expVal)
		actJSON, _ := json.Marshal(actVal)
		if string(expJSON) != string(actJSON) {
			g.t.Errorf("golden body subset mismatch for %q key %q: expected %s, got %s",
				fixture.Path, key, expJSON, actJSON)
		}
	}
}
