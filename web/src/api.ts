// Typed client for the FastAPI KPI endpoints (mirrors api/kpis/router.py models).

/** API origin: the Vite dev proxy locally ('/api'), the Render URL on the public demo. */
export const API_BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? '/api').replace(/\/$/, '')

/** Vite bakes VITE_API_URL into the bundle at BUILD time. A production build made without it has
 *  no API to talk to (on Vercel, /api/* just returns the app's own index.html), so say so plainly. */
export function apiConfigError(env: { PROD: boolean; VITE_API_URL?: string }): string | null {
  if (env.PROD && !env.VITE_API_URL) {
    return 'This build was made without VITE_API_URL. Set it to the API URL in the hosting settings and redeploy.'
  }
  return null
}
export const API_CONFIG_ERROR = apiConfigError(import.meta.env as { PROD: boolean; VITE_API_URL?: string })

/** Turn a FastAPI error response into a readable message (e.g. the demo's 429 text). */
export async function errorMessage(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
  } catch { /* not JSON */ }
  return `${res.status} ${res.statusText}`
}

export interface Meta { as_of: string; seed: number; first_month: string }
export interface Property {
  id: number; name: string; city: string; state: string
  property_type: string; year_built: number; units: number
}
export interface OccupancyRow {
  property_id: number; property: string; units: number; occupied: number; occupancy: number
}
export interface Occupancy {
  as_of: string; by_property: OccupancyRow[]
  trend: { month: string; occupancy: number | null }[]
}
export interface AgingRow {
  bucket: '0-30' | '31-60' | '61-90' | '90+'; current_resident: boolean
  amount: number; tenants: number
}
export interface ExpirationRow {
  month: string; property_id: number; property: string; leases: number; monthly_rent: number
}
export interface NoiRow {
  property_id: number; property: string; month: string; revenue: number
  operating_expenses: number; maintenance: number; noi: number
}
export interface SlaRow {
  grp: string; tickets: number; judged: number; met: number
  sla_rate: number | null; median_hours: number | null
}
export interface RentRollRow {
  property: string; unit_id: number; unit_number: string; unit_type: string; sqft: number
  market_rent: number; lease_id: number | null; tenant: string | null
  start_date: string | null; end_date: string | null; monthly_rent: number | null; balance: number
}
export interface RentRoll { as_of: string; total: number; rows: RentRollRow[] }

export interface Scope {
  propertyIds: number[] // empty = whole portfolio
  start: string // YYYY-MM-01
  end: string // YYYY-MM-01 (inclusive)
}

export function scopeQuery(scope: Scope, extra: Record<string, string | number> = {}): string {
  const p = new URLSearchParams()
  scope.propertyIds.forEach((id) => p.append('property_id', String(id)))
  p.set('start', scope.start)
  p.set('end', scope.end)
  Object.entries(extra).forEach(([k, v]) => p.set(k, String(v)))
  return p.toString()
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { signal })
  if (!res.ok) throw new Error(await errorMessage(res))
  return (await res.json()) as T
}
