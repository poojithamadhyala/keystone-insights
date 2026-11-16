#!/usr/bin/env bash
# One-time GitHub setup for LeaseLens (requires `gh auth login` with the `workflow` scope).
#   infra/github/bootstrap.sh [repo-name]
# Safe to re-run: existing labels/issues/protection are updated or skipped.
set -euo pipefail
NAME="${1:-leaselens}"
OWNER="$(gh api user --jq .login)"
REPO="$OWNER/$NAME"

# ---------------------------------------------------------------- repo + first push
if ! gh repo view "$REPO" >/dev/null 2>&1; then
  gh repo create "$REPO" --public \
    --description "Property-management reporting app with a Claude agent and weekly digest (synthetic data)"
fi
git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$REPO.git"
git push origin main
git push origin v0.1.0

# Squash-only merges keep main's history one commit per PR.
gh repo edit "$REPO" --enable-squash-merge --enable-merge-commit=false \
  --enable-rebase-merge=false --delete-branch-on-merge --enable-issues

# ---------------------------------------------------------------- protect main
# Solo repo: GitHub doesn't let authors approve their own PRs, so 0 approvals are required, but a
# PR, passing CI (jobs "python" and "web") and linear history are, for admins too.
gh api -X PUT "repos/$REPO/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": {"strict": true, "contexts": ["python", "web"]},
  "enforce_admins": true,
  "required_pull_request_reviews": {"required_approving_review_count": 0, "dismiss_stale_reviews": true},
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON

# ---------------------------------------------------------------- labels
label() { gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force >/dev/null; }
label feature "1d76db" "New user-facing capability"
label bug     "d73a4a" "Something is wrong"
label chore   "c5def5" "Process, tooling, docs, maintenance"
label later   "bfbfbf" "Deferred: out of current scope (see README Future work)"

# ---------------------------------------------------------------- backlog issues
issue() {  # title, labels, body
  if gh issue list --repo "$REPO" --state all --search "\"$1\" in:title" --json title \
       --jq '.[].title' | grep -Fxq "$1"; then
    echo "exists: $1"
  else
    gh issue create --repo "$REPO" --title "$1" --label "$2" --body "$3" >/dev/null
    echo "created: $1"
  fi
}
issue "Lean RAG: one baseline, one improved method" "feature" \
  "Shape: docs/shaping/lean-rag.md. Remove BM25/filters/ladder, switch to fastembed (ONNX), re-run make bench-rag. Release v0.2.0."
issue "RAG eval label spot-check (25 items)" "chore" \
  "Fill verdicts in evals/rag/REVIEW.md, run make rag-review and make bench-rag so label precision appears in BENCHMARKS.md."
issue "AI agent: query_kpis, search_documents, generate_report + chat panel" "feature" \
  "Shape: docs/shaping/agent.md. Streaming chat with citations and Show SQL; eval suite; mocked-LLM CI smoke test. Release v0.3.0."
issue "Weekly portfolio digest with number check" "feature" \
  "Shape: docs/shaping/weekly-digest.md. SQL facts, LLM narrative, number check, preview page, Send now, Slack, weekly cron. Release v0.4.0."
issue "Public demo: Vercel + Render + Neon with spend safeguards" "feature" \
  "Shape: docs/shaping/public-demo.md. Rate limit, max tokens, daily spend cap with cached answers; keys server-side. Release v0.5.0."
issue "Polish: states, responsive, accessibility, README" "feature" \
  "Shape: docs/shaping/polish.md. README with demo link, GIF, walkthrough, architecture, How I built this with Claude Code. Release v1.0.0."
issue "docs/domo.md: how to publish the dashboard as a Domo custom app" "chore" \
  "Optional. Write-up only unless a Domo trial is available."
issue "Feature store (Feast + Redis) and renewal-risk model" "feature,later" \
  "Deferred from the original plan. LightGBM renewal-risk classifier + next-best-action ranking, Feast online/offline store, p50/p95/p99 latency benchmark."
issue "Graph RAG over a Neo4j knowledge graph" "feature,later" \
  "Deferred. Property-Unit-Lease-Tenant and WorkOrder-Vendor graph; multi-hop eval vs vector-only."
issue "Drift monitoring and alerting (Evidently, Prometheus, Grafana)" "feature,later" \
  "Deferred. Data/prediction drift, Alertmanager to Slack with runbooks, MTTD benchmark."
issue "Ray batch embedding and scoring benchmark" "feature,later" \
  "Deferred. Throughput/latency sweep, single-process CPU vs Ray + MPS/CUDA."
issue "Email delivery for the weekly digest" "feature,later" \
  "Deferred: needs a sending provider and sender/domain verification."

# ---------------------------------------------------------------- release v0.1.0
if ! gh release view v0.1.0 --repo "$REPO" >/dev/null 2>&1; then
  awk '/^## \[0.1.0\]/{f=1;next} /^## \[/{f=0} f' CHANGELOG.md > /tmp/leaselens-v0.1.0-notes.md
  gh release create v0.1.0 --repo "$REPO" --title "v0.1.0: data, dashboard, RAG benchmark" \
    --notes-file /tmp/leaselens-v0.1.0-notes.md
fi
echo "done: https://github.com/$REPO"
