# AI agent (basic)

**Problem.** Operators have questions the dashboard doesn't answer directly ("Which Maple
Court units owe more than one month's rent?", "What's the late fee on lease 383?", "Summarize
delinquency at Cedar Commons as a chart"). Today that means asking an analyst to write SQL or
digging through PDFs.

**Who it's for.** Property managers and asset directors. Accounting for ad-hoc AR questions.

**Appetite.** 4 hours.

**Sketch.**
- Anthropic SDK tool-use loop in FastAPI, streamed to the browser over SSE.
- `query_kpis`: Claude writes one SELECT. It's parsed (sqlglot) as a single statement over
  allowlisted `reporting.*` views, with a row limit, and run as `leaselens_ro` (read-only, 5 s
  timeout, no PII). Returns rows plus the SQL.
- `search_documents`: improved retrieval from lean RAG. Returns passages with doc id, title and
  section for citations.
- `generate_report`: returns a chart spec (bar/line, data rows from a prior query) plus a short
  summary. The UI renders it with existing chart components.
- Chat panel: streaming text, citation chips (documents and SQL result sets), "Show SQL" toggle.
- Versioned prompt templates in `/prompts`. Document text is wrapped as untrusted data, and the
  three planted injection documents must not change behavior.
- Eval suite: correctness (answer matches SQL ground truth), citation faithfulness (cited text
  supports the claim), out-of-scope refusal, injection resistance. A mocked-LLM smoke test runs in CI.

**Out of scope.** Memory across sessions, multi-agent setups, write actions, renewal-risk
predictions, graph queries, auth.

**Risks.**
- Text-to-SQL correctness. Mitigation: a schema description with column meanings and KPI
  definitions in the prompt; the tool returns SQL errors to the model so it can retry once.
- Cost. Mitigation: max tokens per turn, max tool calls per question (6), and prompt caching on
  the system prompt and tools.
- Injection through documents. Mitigation: no write tools exist at all, tool output is marked
  untrusted, and an eval checks it.

**Go / no-go.** Go if: 100% of SQL guard tests pass (writes, other schemas and multiple statements
are rejected); the live eval answers at least 80% of the correctness set (real number reported,
whatever it is); 0 of the injection cases follow the injected instruction; CI smoke test green.
No-go → ship `query_kpis` + `search_documents` only and move `generate_report` to the backlog.
