# Publishing the dashboard as a Domo custom app

**Status:** not done; no Domo instance was available. This is how it would be done. Domo's
developer tooling changes over time, so **check each step against Domo's current developer
documentation** before relying on it.

## Why it fits

LeaseLens's dashboard is a static React + Vite build that reads JSON from a few endpoints.
Domo custom apps are static web bundles that read data through Domo's data API. Most of the work
is swapping the data source, not rebuilding the UI.

## Steps

1. **Get the data into Domo.** Load the `reporting` views as Domo DataSets, either through a
   Postgres connector on a schedule or by uploading extracts. Rebuild the KPI SQL
   (`backend/api/kpis/queries.py`) as Domo DataFlows (SQL or Magic ETL), so occupancy, aging,
   expirations, NOI and SLA come out as their own DataSets. The SQL is explicit and commented, so
   this is a translation, not a redesign. The KPI tests' hand-worked fixture
   (`backend/api/tests/conftest.py`) is the acceptance check for the translated logic.
2. **Create the app shell.** Install Domo's app CLI (`ryuu`), `domo login` to the instance, and
   add a `manifest.json` that names the app and maps **aliases** (e.g. `occupancy`, `aging`) to
   the DataSet IDs from step 1.
3. **Swap the data layer.** In `web/src/api.ts`, replace `getJson()`'s `fetch` with Domo's data
   API (`domo.get('/data/v1/<alias>?…')`), behind the same typed functions, so the charts don't
   change. Build with relative asset paths (Vite `base: './'`).
4. **Publish.** `npm run build`, copy `dist/` next to `manifest.json`, `domo publish`, then add
   the app as a card on a Domo page and set its permissions there.

## What doesn't move as-is

- **The agent and the digest** need server-side secrets (Anthropic, Pinecone, Slack). They can't
  run inside a static custom app. Either keep them as the external API, called through a
  server-side path Domo provides so no key reaches the browser, or rebuild the digest as a Domo
  scheduled job. Check which server-side option your Domo plan offers.
- **The read-only role and SQL guard** protect *our* Postgres. In Domo, access is governed by
  Domo's own DataSet permissions and row-level policies (PDP), which would replace them for the
  dashboard path.

## Effort guess (estimate, not measured)

About a day for the dashboard (data mapping, data-layer swap, publish), given access to a Domo
instance and the source data. The agent and digest depend on the server-side option available.
