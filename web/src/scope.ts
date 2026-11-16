import { addMonths } from './format'

export const RANGE_PRESETS = [3, 6, 12, 24] as const
export type RangeMonths = (typeof RANGE_PRESETS)[number]

/** Filters live in the URL so a filtered view is shareable and survives reloads. */
export interface UrlFilters { months: RangeMonths; propertyIds: number[] }

export function parseFilters(params: URLSearchParams): UrlFilters {
  const m = Number(params.get('months'))
  const months = (RANGE_PRESETS as readonly number[]).includes(m) ? (m as RangeMonths) : 12
  const propertyIds = params.getAll('p').map(Number).filter((n) => Number.isInteger(n) && n > 0)
  return { months, propertyIds }
}

export function filtersToParams(f: UrlFilters): URLSearchParams {
  const p = new URLSearchParams()
  if (f.months !== 12) p.set('months', String(f.months))
  f.propertyIds.forEach((id) => p.append('p', String(id)))
  return p
}

/** The `months` months ending with the as-of month. */
export function rangeFor(asOf: string, months: number): { start: string; end: string } {
  const end = `${asOf.slice(0, 7)}-01`
  return { start: addMonths(end, -(months - 1)), end }
}
