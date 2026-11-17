// Plain-English layer: what each number means, and the rules of thumb used to call it healthy.
// Thresholds are judgment calls, shown to users and documented in docs/operator-brief.md.

export type Status = 'good' | 'warn' | 'crit'

export const STATUS_LABEL: Record<Status, string> = {
  good: 'Healthy',
  warn: 'Keep an eye on',
  crit: 'Needs attention',
}

export interface Rule { good: number; warn: number; explain: string }

/** Higher is better for both. A value >= good is Healthy, >= warn is Keep an eye on. */
export const RULES = {
  occupancy: {
    good: 0.95, warn: 0.9,
    explain: 'Healthy at 95% or more rented (a common target for stable apartment buildings); keep an eye on 90–95%; needs attention below 90%.',
  },
  repairsOnTime: {
    good: 0.9, warn: 0.8,
    explain: 'Healthy when 90% or more of repairs finish within their deadline (24 hours for emergencies, up to 14 days for small jobs); keep an eye on 80–90%; needs attention below 80%.',
  },
} satisfies Record<string, Rule>

export function judge(value: number | null | undefined, rule: Rule): Status | null {
  if (value == null || Number.isNaN(value)) return null
  if (value >= rule.good) return 'good'
  if (value >= rule.warn) return 'warn'
  return 'crit'
}

/** What each dashboard number means, for someone outside property management. */
export const PLAIN = {
  occupancy: { label: 'Apartments rented', term: 'Occupancy', help: 'Share of apartments with a tenant today. Empty apartments earn nothing.' },
  noi: { label: 'Profit from operations', term: 'NOI', help: 'Rent collected minus the cost of running the buildings (staff, utilities, repairs, taxes). Before loan payments.' },
  delinquent: { label: 'Unpaid rent', term: 'Delinquency', help: 'Rent that current tenants owe and haven\'t paid yet.' },
  expiring: { label: 'Leases ending soon', term: 'Lease expirations', help: 'Leases that end in the next 3 months. Each one is a chance to renew, or an apartment that may go empty.' },
  repairs: { label: 'Repairs done on time', term: 'Work-order SLA', help: 'Share of repair requests finished within their deadline.' },
} as const
