package delivery

import (
	"strings"
	"unicode"
)

// SEOScore holds computed SEO metrics for a title/description/tags set.
type SEOScore struct {
	Score       float64  `json:"seo_score"`
	Factors     []string `json:"factors"`
	WordCount   int      `json:"word_count"`
	HasNumbers  bool     `json:"has_numbers"`
	HasQuestion bool     `json:"has_question"`
	CharLength  int      `json:"char_length"`
}

// ScoreTitleSEO scores a YouTube title for SEO quality (0–10 scale).
// This mirrors the Python seo_optimizer.score_title_seo logic.
func ScoreTitleSEO(title string) SEOScore {
	s := SEOScore{Score: 10.0, CharLength: len(title)}

	words := strings.Fields(title)
	s.WordCount = len(words)

	var factors []string

	// Length scoring
	switch {
	case len(title) < 20:
		s.Score -= 3.0
		factors = append(factors, "title too short (<20 chars)")
	case len(title) > 100:
		s.Score -= 1.5
		factors = append(factors, "title too long (>100 chars)")
	case len(title) >= 40 && len(title) <= 70:
		factors = append(factors, "optimal title length (40-70)")
	}

	// Word count
	if s.WordCount < 3 {
		s.Score -= 2.0
		factors = append(factors, "too few words (<3)")
	} else if s.WordCount >= 6 && s.WordCount <= 12 {
		factors = append(factors, "good word count (6-12)")
	}

	// Numbers boost engagement
	for _, r := range title {
		if unicode.IsDigit(r) {
			s.HasNumbers = true
			s.Score += 0.5
			factors = append(factors, "contains number (boosts CTR)")
			break
		}
	}

	// Question boost
	if strings.ContainsAny(title, "?") {
		s.HasQuestion = true
		s.Score += 0.3
		factors = append(factors, "contains question mark")
	}

	// Power words
	powerWords := []string{"how", "why", "what", "best", "top", "secret", "truth", "proven", "ultimate"}
	lower := strings.ToLower(title)
	for _, w := range powerWords {
		if strings.Contains(lower, w) {
			s.Score += 0.2
			factors = append(factors, "contains power word: "+w)
			break
		}
	}

	// Caps check (ALL CAPS penalty)
	upperCount := 0
	for _, r := range title {
		if unicode.IsUpper(r) {
			upperCount++
		}
	}
	if s.WordCount > 0 && float64(upperCount)/float64(len(title)) > 0.5 {
		s.Score -= 1.0
		factors = append(factors, "excessive caps")
	}

	s.Score = clamp(s.Score, 1.0, 10.0)
	s.Factors = factors
	return s
}

// SuggestTags returns suggested tags derived from the title and niche.
func SuggestTags(title, niche string, existing []string) []string {
	seen := make(map[string]struct{})
	for _, t := range existing {
		seen[strings.ToLower(t)] = struct{}{}
	}

	tags := append([]string{}, existing...)

	// Add niche as a tag if not already present
	if niche != "" {
		if _, ok := seen[strings.ToLower(niche)]; !ok {
			tags = append(tags, niche)
			seen[strings.ToLower(niche)] = struct{}{}
		}
	}

	// Split title words >= 4 chars as keyword candidates
	for _, w := range strings.Fields(strings.ToLower(title)) {
		w = strings.Trim(w, ".,!?\"'")
		if len(w) >= 4 {
			if _, ok := seen[w]; !ok {
				tags = append(tags, w)
				seen[w] = struct{}{}
			}
		}
		if len(tags) >= 15 {
			break
		}
	}

	return tags
}

func clamp(v, min, max float64) float64 {
	if v < min {
		return min
	}
	if v > max {
		return max
	}
	return v
}
