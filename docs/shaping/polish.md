# Polish

**Problem.** A reviewer forms an opinion in about a minute. Rough edges (spinners that never
stop, blank charts, a cramped phone layout, a README that buries the demo) undo the rest of the
work.

**Who it's for.** Hiring reviewers; operators on a phone.

**Appetite.** 2 hours.

**Sketch.**
- Every view has explicit **loading**, **empty** ("No leases expire in this range") and
  **error** (with retry) states.
- Responsive layout down to 375 px wide: tiles wrap, charts resize, tables scroll horizontally.
- Accessible charts: palette already validated for color-vision deficiency; every chart has a
  table view and text labels; add `aria-label` summaries on chart containers.
- A short "why this chart type" note per chart (in `docs/operator-brief.md`, linked from the UI
  info icon).
- README top: live demo link, GIF (Playwright recording → ffmpeg), 60-second walkthrough script,
  Mermaid architecture diagram, ≤5-command quickstart, benchmark table pulled from BENCHMARKS.md,
  "How I built this with Claude Code", limitations, future work (`later` issues).

**Out of scope.** Redesign, new charts, theming beyond light/dark, i18n.

**Risks.** GIF size: keep it under 5 MB (short, 900 px wide, reduced frame rate).

**Go / no-go.** Go if: a Lighthouse accessibility score ≥ 90 on the overview (number reported as
measured); no layout overflow at 375 px; every README number traces to BENCHMARKS.md.
