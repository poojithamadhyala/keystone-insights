// Phone-width check (375 px): fails if any page scrolls horizontally. Needs the app running
// (make demo). Usage: npm run check-mobile [-- --shots ../docs/screenshots]
import { chromium } from 'playwright'

const BASE = process.env.WEB_URL ?? 'http://localhost:5173'
const shotsDir = process.argv.includes('--shots') ? process.argv[process.argv.indexOf('--shots') + 1] : null
const PAGES = [['home', '/'], ['overview', '/dashboard'], ['property', '/properties/1'], ['digest', '/digest']]

const browser = await chromium.launch()
let failed = false
for (const [name, path] of PAGES) {
  const page = await browser.newPage({ viewport: { width: 375, height: 812 } })
  await page.goto(BASE + path)
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(500)
  const r = await page.evaluate(() => {
    const w = document.documentElement.clientWidth
    const offenders = [...document.querySelectorAll('body *')]
      .filter((el) => el.getBoundingClientRect().right > w + 1 && !el.closest('.overflow-x-auto, .overflow-auto'))
      .map((el) => `${el.tagName.toLowerCase()}${el.className ? '.' + String(el.className).split(' ').slice(0, 2).join('.') : ''}`)
    return { scrollWidth: document.documentElement.scrollWidth, width: w, offenders: [...new Set(offenders)].slice(0, 6) }
  })
  const ok = r.scrollWidth <= r.width
  failed ||= !ok
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${name.padEnd(9)} scrollWidth=${r.scrollWidth} width=${r.width}${ok ? '' : ' offenders: ' + r.offenders.join(', ')}`)
  if (shotsDir) await page.screenshot({ path: `${shotsDir}/mobile-${name}.png` })
  await page.close()
}
await browser.close()
process.exit(failed ? 1 : 0)
