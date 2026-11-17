// Record the README walkthrough GIF: welcome -> dashboard -> drill-down -> agent answer (+ Show SQL) -> digest.
// Needs the app running (WEB_URL, default http://localhost:5173) and ffmpeg. One live agent
// question costs about $0.04. Output: ../docs/demo.gif (kept under ~5 MB).
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readdirSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'

const BASE = process.env.WEB_URL ?? 'http://localhost:5173'
const OUT = process.env.OUT ?? '../docs/demo.gif'
const QUESTION = 'Which properties have the most rent outstanding from current residents?'
const videoDir = mkdtempSync(join(tmpdir(), 'leaselens-video-'))

const browser = await chromium.launch()
const context = await browser.newContext({
  viewport: { width: 1280, height: 760 },
  recordVideo: { dir: videoDir, size: { width: 1280, height: 760 } },
})
const page = await context.newPage()
const pause = (ms) => page.waitForTimeout(ms)

await page.goto(BASE + '/')
await page.getByText('How is the portfolio doing?').waitFor()
await page.waitForSelector('.recharts-surface')
await pause(3500) // welcome page: what it is + health cards
await page.getByRole('link', { name: 'Open the dashboard' }).click()
await page.waitForSelector('.recharts-surface')
await pause(2500) // dashboard: KPI tiles + charts
await page.getByRole('radio', { name: '6m' }).click()
await pause(1500)
await page.mouse.wheel(0, 700)
await pause(1500)
await page.getByRole('link', { name: 'Maple Court' }).first().click() // drill-down
await page.waitForSelector('text=Rent roll')
await pause(2000)
await page.mouse.wheel(0, 900)
await pause(1500)
await page.mouse.wheel(0, -2000)
await page.getByRole('button', { name: /^Ask/ }).click()
await page.getByRole('button', { name: QUESTION }).click()
await page.getByText(/Cost \$/).waitFor({ timeout: 120_000 }) // live answer streams in
await pause(1500)
await page.getByRole('button', { name: 'Show source S1' }).first().click()
await page.getByRole('button', { name: 'Show SQL' }).click()
await pause(3000)
await page.getByRole('button', { name: 'Close assistant' }).click()
await page.getByRole('link', { name: /summary/i }).click()
await page.getByText('Preview (exactly what Slack receives)').waitFor()
await pause(3500)
await context.close()
await browser.close()

const video = join(videoDir, readdirSync(videoDir).find((f) => f.endsWith('.webm')))
// Two-pass palette GIF: 10 fps, 900 px wide. Small enough for a README, sharp enough for text.
const filters = 'fps=10,scale=900:-1:flags=lanczos'
const palette = join(videoDir, 'palette.png')
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', video, '-vf', `${filters},palettegen=max_colors=96`, palette])
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', video, '-i', palette, '-lavfi',
  `${filters} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=4`, OUT])
console.log(`saved ${OUT} (${(statSync(OUT).size / 1e6).toFixed(1)} MB)`)
