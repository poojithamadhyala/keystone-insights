// Capture README screenshots from the running stack: `npm run screenshots` (needs `make demo`).
import { mkdirSync } from 'node:fs'
import { chromium } from 'playwright'

const BASE = process.env.WEB_URL ?? 'http://localhost:5173'
const OUT = process.env.OUT_DIR ?? '../docs/screenshots'
const shots = [
  { name: 'home', path: '/', wait: 'How is the portfolio doing?' },
  { name: 'overview', path: '/dashboard' },
  { name: 'property', path: '/properties/1' },
  { name: 'digest', path: '/digest', wait: 'Preview (exactly what Slack receives)' },
  // Live agent call (costs a few cents): opens the panel and asks a suggested question.
  { name: 'agent-chart', path: '/dashboard', chat: 'Show occupancy by property as a bar chart.' },
  { name: 'agent-sql', path: '/dashboard', chat: 'Which properties have the most rent outstanding from current residents?', cite: 'S1' },
]

mkdirSync(OUT, { recursive: true })
const browser = await chromium.launch()
for (const s of shots) {
  const page = await browser.newPage({
    viewport: { width: 1360, height: 900 },
  })
  await page.goto(BASE + s.path)
  await page.waitForLoadState('networkidle')
  if (s.wait) await page.getByText(s.wait).waitFor()
  else await page.waitForSelector('.recharts-surface')
  if (s.chat) {
    if (process.env.SKIP_AGENT) { await page.close(); continue }
    await page.getByRole('button', { name: 'Ask LeaseLens' }).click()
    await page.getByRole('button', { name: s.chat }).click()
    await page.getByText(/Cost \$/).waitFor({ timeout: 120_000 })
    if (s.cite) {
      await page.getByRole('button', { name: `Show source ${s.cite}` }).first().click()
      await page.getByRole('button', { name: 'Show SQL' }).click()
    }
    await page.locator('aside').screenshot({ path: `${OUT}/${s.name}.png` })
    console.log(`saved ${OUT}/${s.name}.png`)
    await page.close()
    continue
  }
  await page.screenshot({ path: `${OUT}/${s.name}.png`, fullPage: true })
  console.log(`saved ${OUT}/${s.name}.png`)
  await page.close()
}
await browser.close()
