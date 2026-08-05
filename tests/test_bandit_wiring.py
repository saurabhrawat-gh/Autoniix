"""Static guards: ensure the bandit pick actually steers the script v1
prompt (Phase 5 polish).

Pre-polish, ``thompson_sample`` was called *after* script generation, so
the chosen arm was recorded but never influenced the LLM. This test
locks in the corrected order so a future refactor doesn't silently
regress the loop closure.

Static-source asserts beat a runtime test here: a runtime test would
need to spin up Postgres + a fake LLM, while a single line-order check
catches the same regression in milliseconds.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SCRIPT_MAIN = Path(__file__).resolve().parents[1] / "src" / "services" / "script" / "main.py"


@pytest.fixture(scope="module")
def src() -> str:
    return SCRIPT_MAIN.read_text()


def _line_of(src: str, needle: str) -> int:
    """Return the 1-based line number of ``needle`` (first match), or -1."""
    for i, line in enumerate(src.splitlines(), 1):
        if needle in line:
            return i
    return -1


def _first_index(src: str, needle: str) -> int:
    """Character-offset index of ``needle`` in ``src``, or -1. Handy for
    robust ordering checks when the call spans multiple lines."""
    return src.find(needle)


def test_bandit_sampled_before_script_generation(src: str):
    """thompson_sample must run before the LLM router call for script v1.

    Uses character-offset matching so it tolerates multi-line argument
    formatting (Phase 10 added a ``channel_id`` kwarg which split the
    call across lines).
    """
    bandit_idx = _first_index(src, "script.bandit_pre_generation")
    route_idx = _first_index(src, 'category="llm.script"')
    assert bandit_idx >= 0, "expected pre-generation bandit sampling"
    assert route_idx >= 0, "expected llm.script router call"
    assert bandit_idx < route_idx, (
        "Bandit must be sampled before the router call so its choice actually steers the prompt."
    )
    hook_idx = _first_index(src, '"hook_style"')
    assert 0 <= hook_idx < route_idx, "hook_style bandit must be invoked before the router"


def test_bandit_choice_is_injected_into_system_prompt(src: str):
    """The selected arm names must end up in the system prompt string."""
    assert "BANDIT GUIDANCE" in src, "expected the prompt to receive an explicit bandit guidance block"
    assert "{selected_hook_style}" in src
    assert "{selected_pacing}" in src


def test_step5_no_longer_re_samples(src: str):
    """The original Step-5 sampler should be a no-op (or removed); a
    second call to ``thompson_sample`` for hook_style would mean we're
    paying twice and risking a second arm being recorded as the chosen
    one for downstream feature storage."""
    occurrences = src.count('thompson_sample(niche, "hook_style"')
    assert occurrences == 0, (
        "Step-5 hook_style sampler is still active \u2014 the bandit was moved "
        "upstream; the old call site should be deleted/no-op."
    )


def test_starter_topics_field_on_channel_create(src: str):
    """Sanity: the channel-create payload must accept starter_topics so
    template-driven onboarding can seed the topics_queue."""
    dashboard = SCRIPT_MAIN.parent.parent / "dashboard" / "main.py"
    text = dashboard.read_text()
    assert "starter_topics" in text
    assert "topics_queue" in text, "expected the create_channel SQL to write topics_queue"
