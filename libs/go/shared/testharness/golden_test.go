package testharness

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestGoldenLoader_LoadAndList(t *testing.T) {
	dir := t.TempDir()

	// Write a fixture
	fixture := GoldenFixture{
		Method: "GET",
		Path:   "/api/v2/auth/mode",
		Status: 200,
		Body:   json.RawMessage(`{"mode":"email"}`),
	}
	data, _ := json.Marshal(fixture)
	_ = os.MkdirAll(filepath.Join(dir, "auth"), 0o755)
	_ = os.WriteFile(filepath.Join(dir, "auth", "auth_mode.json"), data, 0o644)

	loader := NewGoldenLoader(t, dir)

	// Load
	loaded := loader.Load("auth/auth_mode")
	if loaded.Method != "GET" {
		t.Errorf("expected method GET, got %s", loaded.Method)
	}
	if loaded.Status != 200 {
		t.Errorf("expected status 200, got %d", loaded.Status)
	}

	// List
	names := loader.List()
	if len(names) != 1 {
		t.Errorf("expected 1 fixture, got %d", len(names))
	}
	if names[0] != "auth/auth_mode" {
		t.Errorf("expected auth/auth_mode, got %s", names[0])
	}
}

func TestGoldenLoader_AssertBodySubset_Pass(t *testing.T) {
	loader := &GoldenLoader{t: t, dir: "."}

	fixture := &GoldenFixture{
		Path:   "/api/v2/auth/mode",
		Status: 200,
		Body:   json.RawMessage(`{"mode":"email"}`),
	}
	actual := map[string]interface{}{
		"mode":    "email",
		"extra":   "ignored",
	}
	loader.AssertBodySubset(fixture, actual)
}

func TestGoldenLoader_AssertBodySubset_IgnoreFields(t *testing.T) {
	loader := &GoldenLoader{t: t, dir: "."}

	fixture := &GoldenFixture{
		Path:         "/api/v2/me",
		Status:       200,
		Body:         json.RawMessage(`{"user_id":1,"email":"test@example.com"}`),
		IgnoreFields: []string{"user_id"},
	}
	actual := map[string]interface{}{
		"user_id": 99, // different but ignored
		"email":   "test@example.com",
	}
	loader.AssertBodySubset(fixture, actual)
}
