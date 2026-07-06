package delivery_test

import (
	"testing"

	delivery "github.com/autoniix/autoniix/go/service-delivery"
)

func TestScoreTitleSEO_ShortTitle(t *testing.T) {
	r := delivery.ScoreTitleSEO("Hi")
	if r.Score >= 7 {
		t.Errorf("short title should score low, got %.1f", r.Score)
	}
}

func TestScoreTitleSEO_OptimalTitle(t *testing.T) {
	r := delivery.ScoreTitleSEO("How to Build the Best YouTube Channel in 2024")
	if r.Score < 7 {
		t.Errorf("good title should score >= 7, got %.1f", r.Score)
	}
	if !r.HasNumbers {
		t.Error("expected HasNumbers=true for title with '2024'")
	}
}

func TestScoreTitleSEO_Question(t *testing.T) {
	r := delivery.ScoreTitleSEO("Why does this actually work?")
	if !r.HasQuestion {
		t.Error("expected HasQuestion=true")
	}
}

func TestScoreTitleSEO_Clamp(t *testing.T) {
	r := delivery.ScoreTitleSEO("X")
	if r.Score < 1.0 {
		t.Errorf("score should not go below 1.0, got %.1f", r.Score)
	}
}

func TestSuggestTags_DeduplicatesExisting(t *testing.T) {
	tags := delivery.SuggestTags("Python tutorial for beginners", "programming", []string{"python", "tutorial"})
	seen := make(map[string]int)
	for _, t := range tags {
		seen[t]++
	}
	for tag, count := range seen {
		if count > 1 {
			t.Errorf("duplicate tag %q", tag)
		}
	}
}

func TestSuggestTags_AddsNiche(t *testing.T) {
	tags := delivery.SuggestTags("Some video", "cooking", nil)
	found := false
	for _, t := range tags {
		if t == "cooking" {
			found = true
		}
	}
	if !found {
		t.Error("expected niche 'cooking' to appear in suggested tags")
	}
}
