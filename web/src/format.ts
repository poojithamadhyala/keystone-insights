const usd0 = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const usdCompact = new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1,
})

export const money = (v: number): string => usd0.format(v)
export const moneyCompact = (v: number): string => usdCompact.format(v)
export const pct = (v: number | null | undefined, digits = 1): string =>
  v == null ? '—' : `${(v * 100).toFixed(digits)}%`

/** '2026-03-01' -> 'Mar 2026' (parsed as UTC so the month never shifts by timezone). */
export function monthLabel(iso: string, short = false): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`)
  return d.toLocaleDateString('en-US', {
    month: 'short', year: short ? '2-digit' : 'numeric', timeZone: 'UTC',
  })
}

/** First-of-month ISO date n months from `iso`. */
export function addMonths(iso: string, n: number): string {
  const [y, m] = iso.split('-').map(Number)
  const total = y * 12 + (m - 1) + n
  const yy = Math.floor(total / 12)
  const mm = (total % 12) + 1
  return `${yy}-${String(mm).padStart(2, '0')}-01`
}
