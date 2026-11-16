// Capture README screenshots from the running stack: `npm run screenshots` (needs `make demo`).
import { mkdirSync } from 'node:fs'
import { chromium } from 'playwright'

const BASE = process.env.WEB_URL ?? 'http://localhost:5173'
const OUT = process.env.OUT_DIR ?? '../docs/screenshots'
const shots = [
  { name: 'overview', path: '/' },
  { name: 'property', path: '/properties/1' },
  { name: 'overview-dark', path: '/', dark: true },
]

mkdirSync(OUT, { recursive: true })
const browser = await chromium.launch()
for (const s of shots) {
  const page = await browser.newPage({
    viewport: { width: 1360, height: 900 },
    colorScheme: s.dark ? 'dark' : 'light',
  })
  await page.goto(BASE + s.path)
  await page.waitForLoadState('networkidle')
  await page.waitForSelector('.recharts-surface')
  await page.screenshot({ path: `${OUT}/${s.name}.png`, fullPage: true })
  console.log(`saved ${OUT}/${s.name}.png`)
  await page.close()
}
await browser.close()
