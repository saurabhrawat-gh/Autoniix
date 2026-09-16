# Harness — Self-improvement layers

Companion to ADR-005. Describes the four self-improvement components layered
on top of the base harness.

## E1 — Evaluation harness (implemented)

- `tests/prompt_eval/manifest.yaml` — authoritative list of eval cases with
  per-case owner, agent tag, regression thresholds.
- `tests/prompt_eval/cases/*.json` — golden cases (input + expected + spec).
- `scripts/run_prompt_eval.py` — executes each case against the LLM router
  (mock_llm by default; real providers in nightly). Writes results to
  `.harness/eval/<sha>.json`.
- `scripts/eval_regression_check.py` — diffs latest run vs
  `.harness/eval/baseline.json`. Fails on:
  - pass-rate drop > 5% (configurable per case)
  - previously-passing case now fails
  - avg LLM-judge score drop > 0.1
- Wired to `ci.yml` (blocking) and `harness-nightly.yml` (advisory + artifact).

## E2 — Agent versioning (implemented)

- `shared/python/agents/base.py::BaseAgent` now requires `PROMPT_VERSION`
  and `MODEL_ID` class attributes, plus a `harness_hook()` classmethod
  returning discovery metadata.
- Change contract: any prompt or model change bumps the version. The eval
  harness scores the new version; PR merges only when not-worse.
- Future: add `shared/python/agents/CHANGELOG.md` tracking version deltas
  and their eval scores per version.

## E3 — Sentry auto-fix agent, closed-loop (scaffolded)

Location: `backend/platform/sentry-agent/fix_agent.py`.

Target behaviour (not yet implemented — tracked as follow-up work):

1. Sentry issue → triage → LLM fix proposal → Draft PR.
2. Sandbox container checkout → `bash scripts/ci-local.sh --full --docker`.
3. Prompt-eval + regression check.
4. On both green: mark PR ready-for-review + label `harness:verified`.
5. On red: close PR with diagnostic comment.
6. Add a regression golden case to `tests/prompt_eval/cases/regressions/`
   so the same bug cannot silently regress.

Implementation notes: reuse the `apply-branch-protection.sh` gh api pattern;
target `develop` branch only; require human "Ready for review" click even
when `harness:verified` is set.

## E4 — Static self-detection (partially implemented)

- Nightly workflow `.github/workflows/harness-nightly.yml` runs:
  - `semgrep` with `p/ci p/python p/typescript p/security-audit` (SARIF).
  - `pip-audit` (advisory).
  - `npm audit --omit=dev` (advisory).
  - `mutmut` scoped to `shared/python/agents/` (advisory).
- To promote to blocking: move the specific step from `harness-nightly.yml`
  into the corresponding `ci.yml` job and remove `continue-on-error`.

## E5 — ML retrain trigger (scaffolded)

Existing pieces already in the repo:

- `scripts/trigger_first_retrain.py`
- `scripts/generate_training_data.py`
- `backend/api/core/brain/scorer.py`

Target behaviour (follow-up):

- Weekly Temporal schedule (register via `scripts/register_schedules.py`).
- Aggregate production retention features → dataset artefact under
  `.harness/datasets/<date>/`.
- Retrain calibrator/scorer in shadow mode.
- Run eval harness against golden data.
- Auto-promote iff regression check passes; otherwise notify via Slack.

## Directory conventions

```
.harness/
├── reports/<sha>.json          harness-report output (Phase A)
├── deploys/<sha>.ok            pre-deploy sentinel (Phase D)
├── bypass.log                  audit log of hook bypasses (Phase G)
├── eval/
│   ├── <sha>.json              a single eval run
│   ├── baseline.json           last known-good aggregate
│   └── regression-report.json  output of eval_regression_check.py
├── nightly/<run_id>/           uploaded artifacts from harness-nightly
└── datasets/<date>/            retrain artefacts (E5)
```

All `.harness/` state is gitignored (see `.gitignore`).
