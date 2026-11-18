# Deploying the public demo

Free tiers only: **Neon** (Postgres), **Render** (API, Docker), **Vercel** (web). Pinecone is the
same index used locally. About 30 minutes the first time. Every secret goes into a provider
dashboard. Nothing secret is committed, and the web bundle is scanned in CI (`npm run check-bundle`).

```
Browser ──► Vercel (static React build) ──► Render (FastAPI, Docker) ──► Neon (Postgres)
                                                   ├──► Anthropic (Claude)
                                                   └──► Pinecone (documents)
GitHub Actions (weekly cron) ──► POST /digest/run on Render ──► Slack
```

## 1. Database: Neon

1. neon.tech → **New project**. Postgres 16 or 17, region **AWS US East (N. Virginia)**, the same
   region as the Render service in `render.yaml`.
2. **Connection details** → turn **off** "Connection pooling", then copy the connection string
   (`postgresql://…?sslmode=require`). Migrations and the bulk `COPY` used by seeding need a
   direct connection.
3. Seed it from your laptop (migrations + about 100k synthetic rows, about 23 MB, under a minute):
   ```bash
   DATABASE_URL='postgresql://…' make seed-remote
   ```
   Neon's user isn't a superuser. Migration 0004 grants it the read-only role so the agent's
   `SET LOCAL ROLE` works (DECISIONS.md D-043; covered by `test_managed_postgres.py`).

## 2. API: Render

1. render.com → **New → Blueprint** → pick this GitHub repo. Render reads `render.yaml`.
2. Fill in the secrets it asks for. **Then open the service → Environment and check that all
   five exist.** On our first deploy Render did not prompt for every `sync: false` key
   (`DIGEST_RUN_TOKEN` was missed), and a missing one fails quietly later.

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Neon string from step 1 |
   | `ANTHROPIC_API_KEY`, `PINECONE_API_KEY` | same as your `.env` |
   | `DIGEST_RUN_TOKEN` | same as your `.env` |
   | `SLACK_WEBHOOK_URL` | same as your `.env` |

   `CORS_ORIGINS` and `CORS_ORIGIN_REGEX` aren't secrets, so they're set in `render.yaml`. If you
   fork this repo, change them to your Vercel project's URL (see step 3).

3. **Apply**. The first build takes several minutes (it bakes the ONNX models into the image).
   When it's live, open `https://<service>.onrender.com/health`. Expect
   `{"status":"ok","demo_mode":true,"send_enabled":false}`.
4. Build the first digest preview once (about one cent):
   `curl -X POST https://<service>.onrender.com/digest/build`

The free plan sleeps after about 15 idle minutes. The first visit afterwards takes up to a minute,
and the web app shows "Waking up the demo API…" meanwhile.

## 3. Web: Vercel

1. vercel.com → **Add New → Project** → import this repo.
2. **Root Directory: `web`**. The framework (Vite), build command and SPA routing come from
   `web/vercel.json`.
3. **Before clicking Deploy**, open *Environment Variables* and add `VITE_API_URL` =
   `https://<service>.onrender.com` (no trailing slash). Vite bakes it into the JavaScript **at
   build time**. If the first build ran without it, add it and use **Deployments → ⋯ → Redeploy**.
   Changing the variable alone doesn't affect a build that already exists. A build without it now
   shows "This build was made without VITE_API_URL…" instead of loading forever.
4. **Deploy**, then copy the production URL (e.g. `https://keystone-insights-nu.vercel.app`).
5. Update `CORS_ORIGINS` (exact production URL, `https://…`, no trailing slash) and
   `CORS_ORIGIN_REGEX` (preview URLs) in `render.yaml` if they differ, merge, and Render redeploys.

**CORS and preview deployments.** Browsers send `Origin: https://host` and CORS needs an exact
match. That's why the production URL needs `https://` (the API now adds it if it's missing).
Vercel also gives every deployment its own URL (`keystone-insights-<hash>-<team>.vercel.app`);
those are allowed by `CORS_ORIGIN_REGEX`. CORS isn't the security boundary here: the API is
public and unauthenticated by design, and what protects it is the rate limits and spend cap.

## 4. Weekly digest schedule

GitHub repo → **Settings → Secrets and variables → Actions**:
- `DIGEST_API_URL` = `https://<service>.onrender.com`
- `DIGEST_RUN_TOKEN` = same value as on Render

Then **Actions → weekly-digest → Run workflow**. It should post this week's digest to Slack and
finish green. (`DIGEST_SEND_ENABLED=false` only disables the button for visitors; the
token-protected schedule still sends.)

## 5. Acceptance checks (go/no-go from `docs/shaping/public-demo.md`)

- [ ] Fresh private browser window: the dashboard loads (after the wake-up screen if asleep)
- [ ] "Ask LeaseLens" answers a suggested question with citations; the cost line shows
- [ ] The 11th question within an hour from the same browser gets the "Demo limit reached" message
- [ ] /digest shows the preview; **Send now** is disabled with the demo note
- [ ] Render → **Metrics**: memory after a document question stays under 512 MB (record the
      number in DECISIONS.md)
- [ ] Cold start: after 15+ idle minutes, time the first request:
      `curl -o /dev/null -s -w '%{time_total}s\n' https://<service>.onrender.com/health`
- [ ] CI's "bundle scan: clean" step passed on main

## Safeguards (what protects the API bill)

| Guard | Setting (render.yaml) | Where |
|---|---|---|
| Per-IP agent questions | `AGENT_QUESTIONS_PER_HOUR=10` | `backend/api/safeguards.py` |
| Per-IP digest builds | `DIGEST_BUILDS_PER_HOUR=3` | same |
| Daily Claude spend cap (survives restarts) | `DAILY_SPEND_CAP_USD=2` | `llm_spend` table |
| Per-turn limits | 4,000 output tokens, at most 6 tool rounds, 1,000-character questions | `backend/api/agent/loop.py` |
| Over budget / no key | recorded answers for the suggested questions, labeled | `backend/api/demo_samples.json` |
| Keys | server-side only; bundle scanned in CI | `web/scripts/check-bundle.mjs` |

To re-record the cached answers after changing the prompt, tools or data:
`cd backend && uv run --group rag python -m api.record_samples` (about $0.20).
