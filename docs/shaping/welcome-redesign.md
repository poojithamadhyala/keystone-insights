# Welcome page and plain-English redesign

**Problem.** A reviewer who isn't in property management lands on a dashboard full of industry
terms (NOI, delinquency aging, SLA) with no explanation of what the app is or why it matters. They
can't tell whether the numbers are good or bad, so they leave unimpressed even though the work
behind it is solid.

**Who it's for.** Hiring reviewers and anyone outside property management; secondarily, new
property managers.

**Appetite.** 3 hours.

**Sketch.**
- **Welcome page (`/`).** One-sentence headline ("Your apartment portfolio, explained"), what the
  app is, and that the data is synthetic. Four live **health cards** in plain words: apartments
  rented, rent owed by current residents (with this week's change), leases ending soon, repairs
  done on time. Each shows a status (Healthy / Keep an eye on / Needs attention) with an icon and
  a label, never color alone, and a "how we judge this" rule of thumb. Then three "what you can do
  here" cards (see the numbers, ask a question, read the weekly summary) and three "how the AI is
  kept honest" points.
- **Dashboard (`/dashboard`).** Plain-English tile labels with the industry term kept in
  parentheses ("Profit from operations (NOI)"), a one-line explanation on every tile, and plainer
  chart titles.
- **Visual refresh.** A logo mark, a tinted hero band, a clearer nav (Home · Dashboard · Weekly
  summary · Ask), slightly softer cards. Same tokens, so dark mode and contrast stay intact.

**Out of scope.** New data or endpoints, new charts, animations, a marketing site, changes to the
agent or digest logic.

**Risks.**
- Status thresholds are judgment calls: they live in one tested file (`web/src/health.ts`), are
  shown to the user, and are documented in the operator brief.
- Moving the dashboard to `/dashboard` breaks old links: `/properties/:id` is unchanged, and the
  screenshot, GIF and mobile scripts are updated.
- Accessibility could regress: `make bench-a11y` and `npm run check-mobile` must still pass.

**Go / no-go.** Go if someone with no industry knowledge can say what the app does and whether the
portfolio is healthy within 10 seconds of landing. Lighthouse accessibility stays 100 on all pages
(now four), no horizontal scroll at 375 px, `make check` green.
