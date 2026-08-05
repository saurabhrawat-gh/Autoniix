"""Compare a fresh prompt-eval run against the last known-good baseline.

Fails (exit 1) if:
  * pass-rate for any agent drops by more than `max_pass_rate_regression_pct`
  * any case that used to pass now fails (single-case regression)
  * average LLM-judge score drops by more than `max_avg_score_regression`

Reads:
  .harness/eval/<sha>.json     current run (produced by run_prompt_eval)
  .harness/eval/baseline.json  last known-good aggregate

Writes:
  .harness/eval/regression-report.json

Intentionally has no external deps beyond pyyaml so it runs in CI without
the full ML/LLM stack installed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "tests/prompt_eval/manifest.yaml"
HARNESS_DIR = ROOT / ".harness/eval"


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:  # pragma: no cover
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "pyyaml"])
        import yaml
    return yaml.safe_load(path.read_text())


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _passfail(run: dict) -> dict[str, dict]:
    """Aggregate a run into {agent_id: {pass_rate, avg_score, cases: {...}}}."""
    agents: dict[str, dict] = {}
    for case in run.get("cases", []):
        agent = case.get("agent", case.get("category", "unknown"))
        rec = agents.setdefault(agent, {"pass": 0, "fail": 0, "scores": [], "cases": {}})
        passed = bool(case.get("passed", False))
        rec["cases"][case["id"]] = passed
        if passed:
            rec["pass"] += 1
        else:
            rec["fail"] += 1
        if "score" in case:
            rec["scores"].append(float(case["score"]))
    for agent, rec in agents.items():
        total = rec["pass"] + rec["fail"]
        rec["pass_rate"] = (rec["pass"] / total * 100.0) if total else 0.0
        rec["avg_score"] = (sum(rec["scores"]) / len(rec["scores"])) if rec["scores"] else None
    return agents


def main() -> int:
    manifest = _load_yaml(MANIFEST)
    defaults = manifest.get("defaults", {})
    max_rate = float(defaults.get("max_pass_rate_regression_pct", 5.0))
    max_score = float(defaults.get("max_avg_score_regression", 0.1))
    block_case = bool(defaults.get("block_case_regressions", True))

    current_files = sorted(HARNESS_DIR.glob("*.json"))
    current_files = [f for f in current_files if f.name not in {"baseline.json", "regression-report.json"}]
    if not current_files:
        print("⚠  No eval runs found in .harness/eval/ — nothing to compare.")
        return 0
    current = _load_json(current_files[-1])
    baseline = _load_json(HARNESS_DIR / "baseline.json")

    if not baseline:
        print("ℹ  No baseline yet — establishing current run as baseline.")
        HARNESS_DIR.mkdir(parents=True, exist_ok=True)
        (HARNESS_DIR / "baseline.json").write_text(json.dumps(current, indent=2))
        return 0

    now = _passfail(current)
    prev = _passfail(baseline)
    report = {"regressions": [], "improvements": [], "unchanged": []}
    fatal = False

    for agent, cur in now.items():
        old = prev.get(agent, {})
        pr_delta = old.get("pass_rate", 0.0) - cur["pass_rate"]
        if pr_delta > max_rate:
            report["regressions"].append(
                {
                    "agent": agent,
                    "type": "pass_rate",
                    "before": old.get("pass_rate"),
                    "after": cur["pass_rate"],
                    "delta_pct": -pr_delta,
                }
            )
            fatal = True

        if cur["avg_score"] is not None and old.get("avg_score") is not None:
            sc_delta = old["avg_score"] - cur["avg_score"]
            if sc_delta > max_score:
                report["regressions"].append(
                    {
                        "agent": agent,
                        "type": "avg_score",
                        "before": old["avg_score"],
                        "after": cur["avg_score"],
                        "delta": -sc_delta,
                    }
                )
                fatal = True

        if block_case:
            old_cases = old.get("cases", {})
            for case_id, now_pass in cur.get("cases", {}).items():
                if old_cases.get(case_id, True) and not now_pass:
                    report["regressions"].append(
                        {"agent": agent, "type": "case", "case_id": case_id, "before": "pass", "after": "fail"}
                    )
                    fatal = True

    HARNESS_DIR.mkdir(parents=True, exist_ok=True)
    (HARNESS_DIR / "regression-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if fatal:
        print("\n❌ Eval regression detected — see report above.", file=sys.stderr)
        return 1
    print("\n✅ No eval regression.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
