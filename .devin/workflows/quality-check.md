---
description: Quality check — validate changes against quality gate thresholds and scoring logic
---

# Quality Check Workflow

Run this after making changes to scoring, thresholds, or any service that participates in quality gates.

## Steps

1. **Identify affected quality gates**
   - Which service was modified? Map to its quality gate(s) from the 33-gate table.
   - Check `docs/architecture/05-QUALITY-GATES.md` for the relevant gate's threshold and retry policy.

2. **Verify threshold consistency**
   - If you changed a threshold in code, also update `seed-data.sql` (system_config table).
   - `ON CONFLICT DO UPDATE` means re-seeding applies changes.
   - Verify the threshold in `system_config` matches the hardcoded default.

3. **Check anti-inflation measures**
   - If you modified a scoring prompt, ensure it still contains adversarial instructions.
   - Verify calibration examples are present.
   - Ensure rewrite limits haven't been increased beyond max (script: 3, thumbnail: 2).

4. **Run relevant tests**
   ```bash
   # turbo
   pytest tests/test_*intelligence*.py tests/test_*quality*.py -v
   ```

5. **Verify composite scoring**
   - If you changed any gate weight, recalculate the composite score formula.
   - Composite threshold is 8.5. Changing weights may require adjusting this.
   - Human review triggers when composite < threshold OR any gate < 6.0.

6. **Check prompt registry**
   - If prompts were modified, verify they're in `seed-data.sql` with correct version.
   - `ON CONFLICT (service, prompt_type) DO UPDATE SET prompt_text = EXCLUDED.prompt_text, version = EXCLUDED.version + 1`
