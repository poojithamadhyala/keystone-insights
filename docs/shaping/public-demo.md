# Public demo

**Problem.** A reviewer at the hiring company won't clone a repo and run Docker. They need a link
that works in a browser, without anyone being able to run up an API bill.

**Who it's for.** Hiring reviewers (non-technical and technical).

**Appetite.** 3 hours, plus about 30 minutes of the owner's time creating free accounts.

**Sketch.**
- **Web:** Vercel (static Vite build). `VITE_API_URL` points at the API.
- **API:** Render free web service (Docker). It sleeps when idle, so the web app shows a
  "waking up the demo…" state on a cold start.
- **DB:** Neon free Postgres, migrated and seeded by a one-off job with the same seed.
- **Documents:** the existing Pinecone index.
- **Safeguards (server-side only):** per-IP rate limit (e.g. 10 agent questions per hour),
  `max_tokens` per turn, tool-call cap, and a **daily spend cap of $2** tracked in Postgres from
  `usage` tokens × price. When the cap is hit, users get **cached sample answers** for suggested
  questions, clearly labeled "cached".
- Keys only in Render environment variables. CORS limited to the Vercel origin. The digest
  "Send now" is disabled in the public demo (preview only).

**Out of scope.** Auth, custom domain, paid tiers, autoscaling, multi-region.

**Risks.** Render free tier has 512 MB of RAM; ONNX models plus FastAPI must fit (measured in
lean RAG). Neon cold starts; free-tier limits change without notice (document what was used and
when). A spend cap must not depend on in-memory state, so it is stored in Postgres.

**Go / no-go.** Go if: the link works from a fresh browser; a cold start is handled with a
visible state; the rate limit and spend cap are verified by tests and one manual check; no key
appears in the web bundle (scan the build output). No-go → dashboard-only demo with cached agent
answers.
