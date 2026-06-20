# Devin model aliases — source this in ~/.zshrc
# Usage: d-fe "add a login form"  → starts Devin with Sonnet for frontend
#        d-arch "design the event bus" → starts Devin with Opus for architecture

alias d="devin"

# Task-specific launchers
alias d-fe="devin --model sonnet --"       # Frontend: components, pages, styling
alias d-be="devin --model sonnet --"       # Backend: APIs, services, DB
alias d-arch="devin --model opus --"       # Architecture: system design, workflows
alias d-agent="devin --model opus --"      # Agentic: brain, critic, multi-agent
alias d-fix="devin --model swe --"         # Quick fixes: typos, lint, docs
alias d-debug="devin --model sonnet --"    # Debugging (escalates to Opus if needed)

# Resume last session
alias dr="devin --continue"

# Common task shortcuts
alias d-api="devin --model sonnet -- implement"
alias d-test="devin --model sonnet -- write tests for"
alias d-refactor="devin --model opus -- refactor"
alias d-review="devin --model sonnet -- review"
