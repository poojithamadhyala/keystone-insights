#!/usr/bin/env bash
# Fails if a tracked or staged file contains something that looks like an API key.
# Runs in CI and as a git pre-commit hook (`make hooks`). Patterns: Anthropic (sk-ant-),
# Pinecone (pcsk_), Slack webhooks, AWS access keys.
set -euo pipefail
PATTERN='sk-ant-[A-Za-z0-9_-]{20,}|pcsk_[A-Za-z0-9_]{20,}|hooks\.slack\.com/services/T[A-Z0-9]+/|AKIA[0-9A-Z]{16}'
if git grep -nIE "$PATTERN" -- . ':!infra/check_secrets.sh' ; then
  echo "ERROR: possible secret in a tracked file (see above). Keys belong in .env only." >&2
  exit 1
fi
if git diff --cached --name-only | grep -q . && git diff --cached -U0 | grep -E "^\+" | grep -qE "$PATTERN"; then
  echo "ERROR: possible secret in staged changes. Keys belong in .env only." >&2
  exit 1
fi
echo "secret scan: clean"
