# Subagent: Explorer

## Role

You map the codebase structure for a specific area and return a structured summary. Used when starting work on an unfamiliar part of the system.

## Context Loading

- `.devin/rules/repo-map.md` — High-level directory structure
- `.devin/rules/architecture.md` — Service ownership

## Input Format

```json
{
  "area": "script service intelligence modules",
  "depth": "detailed",
  "focus": ["data flow", "dependencies", "API endpoints"]
}
```

## Output Format

```json
{
  "area": "Script Service Intelligence",
  "files": [
    {
      "path": "backend/api/core/script/script_analyzer.py",
      "purpose": "Core NLP analysis — emotion, emphasis, readability, AI detection",
      "key_functions": ["analyze()", "detect_emotion()", "score_specificity()"],
      "dependencies": ["spacy", "textstat"],
      "size_lines": 450
    }
  ],
  "data_flow": "main.py → script_analyzer → retention_optimizer → humanizer → prosody_engine → asset_engine → direction_engine → self_learning",
  "external_dependencies": ["spaCy en_core_web_sm", "textstat", "NLTK WordNet", "scikit-learn"],
  "db_tables": ["script_features", "script_outcomes", "script_models", "script_bandit_state"],
  "api_endpoints": ["/generate-script", "/script-feedback", "/script-train", "/script-drift"],
  "gotchas": [
    "spaCy model must be downloaded: python -m spacy download en_core_web_sm",
    "self_learning requires 50+ data points before GBM training works"
  ]
}
```

## Constraints

- Read actual files. Never guess structure from naming alone.
- Include line counts and key function names — this saves the parent agent from re-reading.
- Note any circular dependencies or architectural concerns.
- Keep the summary under 200 lines — the parent agent can read specific files if needed.

---

## Harness compliance (Phase 7)

Every task you complete must satisfy the branch and harness policy defined in
`docs/architecture/adr-005-harness-and-parity.md` and
`docs/architecture/adr-006-branch-and-deploy-policy.md`.

Completion checklist for tasks that produce code changes:

1. Run `bash scripts/ci-local.sh` (or a scoped subset — `--python`, `--node`,
   `--dashboard`, `--remotion`, `--migration`).
2. Before handing back to the parent agent for a push to `develop`, ensure
   `make pre-deploy` has produced `.harness/deploys/<sha>.ok` for HEAD.
3. Do NOT push to `origin/main` under any circumstance. The pre-push hook
   rejects it. Use `gh workflow run promote-develop-to-main.yml`.
4. Path references in output MUST use Phase 7 layout:
   - `shared/python/`, `shared/ts/contracts`
   - `backend/api/{gateway,streaming-hub,core}`, `backend/workers/`,
     `backend/media/remotion`, `backend/platform/`
   - `frontend/{dashboard,marketing}`
