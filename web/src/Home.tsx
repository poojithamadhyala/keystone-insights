import { MotionConfig, motion, useReducedMotion } from 'motion/react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { AgingRow, ExpirationRow, Meta, Occupancy, Property, Scope, SlaRow } from './api'
import { scopeQuery } from './api'
import { agingByBucket, expirationsByMonth } from './charts'
import { useChat } from './chat'
import { StatusBadge } from './components'
import { money, moneyCompact, pct } from './format'
import { judge, PLAIN, RULES, type Status } from './health'
import { rangeFor } from './scope'
import { useApi } from './useApi'

interface DigestFacts {
  as_of: string
  delinquency: { change: number }
  sla: { open_breaches: number }
}

const REPO = 'https://github.com/poojithamadhyala/keystone-insights'
const EASE = [0.22, 1, 0.36, 1] as const // slow, confident deceleration

/** Fade up 24px once, when scrolled into view. */
function Reveal({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div className={className} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-80px' }} transition={{ duration: 1, ease: EASE, delay }}>
      {children}
    </motion.div>
  )
}

/** Counts up once when it first scrolls into view; shows the final value immediately when motion
 *  is reduced or IntersectionObserver isn't available. */
function CountUp({ value, format }: { value: number | null; format: (v: number) => string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const reduced = useReducedMotion()
  const [shown, setShown] = useState<number | null>(null)
  useEffect(() => {
    if (value == null) return
    const el = ref.current
    if (reduced || typeof IntersectionObserver === 'undefined' || !el) {
      const id = requestAnimationFrame(() => setShown(value))
      return () => cancelAnimationFrame(id)
    }
    let raf = 0
    const io = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return
      io.disconnect()
      const start = performance.now()
      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / 1600)
        setShown(value * (1 - (1 - t) ** 3))
        if (t < 1) raf = requestAnimationFrame(tick)
      }
      raf = requestAnimationFrame(tick)
    }, { threshold: 0.4 })
    io.observe(el)
    return () => { io.disconnect(); cancelAnimationFrame(raf) }
  }, [value, reduced])
  return <span ref={ref} className="tabular">{value == null ? '…' : format(shown ?? 0)}</span>
}

function Figure({ title, term, value, format, detail, help, status, rule }: {
  title: string; term: string; value: number | null; format: (v: number) => string
  detail?: ReactNode; help: string; status?: Status | null; rule?: string
}) {
  return (
    <div role="group" aria-label={title} className="border-t border-brand pt-6">
      {/* two lines reserved so the four figures share one baseline even when a label wraps */}
      <h3 className="min-h-12 font-sans text-base font-normal text-ink-2">{title} <span className="text-muted">({term})</span></h3>
      <p className="display mt-3 text-[56px] leading-none text-ink"><CountUp value={value} format={format} /></p>
      {detail && <p className="mt-3 text-base text-ink-2">{detail}</p>}
      {status && <p className="mt-3"><StatusBadge status={status} title={rule} /></p>}
      <p className="mt-4 text-sm leading-relaxed text-muted">{help}</p>
    </div>
  )
}

/** One full-width row: image on one side (alternating), words on the other. The image reveals
 *  with a bottom-to-top clip; the text fades in after it. */
function Row({ image, alt, flip, label, name, place, children, facts, action }: {
  image: string; alt: string; flip?: boolean; label: string; name: string; place: string
  children: ReactNode; facts: string; action: ReactNode
}) {
  return (
    <article className="grid items-center gap-10 md:grid-cols-2 md:gap-20">
      <motion.div className={`aspect-[4/5] overflow-hidden ${flip ? 'md:order-2' : ''}`}
                  initial={{ clipPath: 'inset(100% 0 0 0)' }} whileInView={{ clipPath: 'inset(0% 0 0 0)' }}
                  viewport={{ once: true, margin: '-100px' }} transition={{ duration: 1.1, ease: EASE }}>
        <img src={image} alt={alt} loading="lazy" className="h-full w-full object-cover" />
      </motion.div>
      <Reveal delay={0.5} className={flip ? 'md:order-1' : ''}>
        <p className="label text-brand">{label}</p>
        <h3 className="mt-5 text-[clamp(32px,3.4vw,52px)] leading-[1.08] text-ink">{name}</h3>
        <p className="label mt-3 text-muted">{place}</p>
        <div className="mt-6 max-w-md text-ink-2">{children}</div>
        <p className="mt-6 border-t border-line pt-4 text-sm text-muted">{facts}</p>
        <div className="mt-8">{action}</div>
      </Reveal>
    </article>
  )
}

export function Home() {
  const { openChat } = useChat()
  const [showRules, setShowRules] = useState(false)
  const meta = useApi<Meta>('/kpis/meta')
  // Same 12-month window and endpoints as the dashboard, so the two pages always agree.
  const scope: Scope | null = meta.data ? { propertyIds: [], ...rangeFor(meta.data.as_of, 12) } : null
  const q = (path: string, extra?: Record<string, string | number>) => (scope ? `${path}?${scopeQuery(scope, extra)}` : null)
  const occ = useApi<Occupancy>(q('/kpis/occupancy'))
  const aging = useApi<AgingRow[]>(q('/kpis/delinquency'))
  const exp = useApi<ExpirationRow[]>(q('/kpis/lease-expirations', { months: 12 }))
  const sla = useApi<SlaRow[]>(q('/kpis/work-order-sla', { group_by: 'priority' }))
  const properties = useApi<Property[]>('/kpis/properties')
  const digest = useApi<{ facts: DigestFacts }>('/digest/latest') // optional: weekly change

  const rows = occ.data?.by_property ?? []
  const units = rows.reduce((s, r) => s + r.units, 0)
  const occupied = rows.reduce((s, r) => s + r.occupied, 0)
  const occRate = occ.data ? (units ? occupied / units : null) : null
  const owed = aging.data ? agingByBucket(aging.data).reduce((s, r) => s + r.current, 0) : null
  const next3 = expirationsByMonth(exp.data ?? []).slice(0, 3)
  const ending = exp.data ? next3.reduce((s, r) => s + r.leases, 0) : null
  const atStake = next3.reduce((s, r) => s + r.monthly_rent, 0)
  const met = (sla.data ?? []).reduce((s, r) => s + r.met, 0)
  const judged = (sla.data ?? []).reduce((s, r) => s + r.judged, 0)
  const onTime = sla.data ? (judged ? met / judged : null) : null
  const facts = digest.data?.facts.as_of === meta.data?.as_of ? digest.data?.facts : undefined
  const city = new Map((properties.data ?? []).map((p) => [p.id, `${p.city}, ${p.state}`]))
  const largest = [...rows].sort((a, b) => b.units - a.units).slice(0, 5)

  if (meta.error) {
    return (
      <div role="alert" className="mx-auto max-w-[1320px] space-y-4 px-5 pt-[140px] md:px-10">
        <p className="text-critical">Couldn't reach the API: {meta.error}</p>
        <button type="button" onClick={meta.reload} className="btn btn-sm">Retry</button>
      </div>
    )
  }

  return (
    <MotionConfig reducedMotion="user">
      {/* Hero: full-bleed photo, the only gradient on the site, text block bottom left. */}
      <section className="relative flex min-h-[clamp(620px,88vh,940px)] items-end overflow-hidden">
        <motion.img src="/images/hero-facade-dusk.jpg" alt="" aria-hidden
                    className="absolute inset-0 h-full w-full object-cover"
                    initial={{ scale: 1.06 }} animate={{ scale: 1 }} transition={{ duration: 2.4, ease: EASE }} />
        {/* The site's only gradient. Desktop: charcoal from bottom left fading to the top right.
            Narrow screens: the text spans the full width, so the overlay rises from the bottom
            instead and the copy never sits on the bright fins. */}
        <div aria-hidden className="absolute inset-0 hidden md:block"
             style={{ background: 'linear-gradient(to top right, rgba(20,20,19,0.94) 0%, rgba(20,20,19,0.86) 42%, rgba(20,20,19,0.22) 74%, rgba(20,20,19,0) 100%)' }} />
        <div aria-hidden className="absolute inset-0 md:hidden"
             style={{ background: 'linear-gradient(to top, rgba(20,20,19,0.96) 0%, rgba(20,20,19,0.86) 55%, rgba(20,20,19,0.45) 100%)' }} />
        <div className="relative mx-auto w-full max-w-[1320px] px-5 pb-16 md:px-10 md:pb-24">
          <motion.div className="max-w-3xl" initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 1.2, ease: EASE, delay: 0.3 }}>
            <p className="label text-brand">Apartment portfolio reporting, with an AI analyst</p>
            <h1 className="mt-6 text-[clamp(40px,5.6vw,92px)] leading-[1.04] text-ink">
              Your apartment portfolio, explained.
            </h1>
            <p className="mt-6 max-w-xl text-ink-2">
              Plain answers about how full the buildings are, who is behind on rent and whether
              repairs happen on time. Every number shows where it came from.
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-8">
              <Link to="/dashboard" className="btn">Open the dashboard</Link>
              <button type="button" onClick={openChat} className="link-line">Ask a question</button>
            </div>
          </motion.div>
        </div>
      </section>

      <div className="mx-auto max-w-[1320px] px-5 md:px-10">
        {/* Intro */}
        <section className="py-[clamp(88px,10vw,140px)] text-center">
          <Reveal>
            <p className="display mx-auto max-w-4xl text-[clamp(24px,2.6vw,34px)] leading-[1.45] text-ink">
              LeaseLens turns a property company's everyday data into plain answers, and lets anyone
              ask it questions in ordinary English.
            </p>
            <p className="mx-auto mt-8 max-w-2xl text-muted">
              {rows.length || 20} buildings · {units ? units.toLocaleString() : '3,000'} apartments ·
              data as of {meta.data?.as_of ?? '…'} · <span className="text-ink-2">all data is made up for this demo</span>
            </p>
          </Reveal>
        </section>

        {/* Numbers */}
        <section aria-labelledby="health-h" className="pb-[clamp(88px,10vw,140px)]">
          <Reveal className="flex flex-wrap items-end justify-between gap-6">
            <div>
              <p className="label text-brand">As of {meta.data?.as_of ?? '…'}</p>
              <h2 id="health-h" className="mt-4 text-[clamp(32px,3.4vw,52px)] leading-[1.08] text-ink">How is the portfolio doing?</h2>
            </div>
            <button type="button" onClick={() => setShowRules((v) => !v)} aria-expanded={showRules} className="link-line">
              How we judge "healthy"
            </button>
          </Reveal>
          {showRules && (
            <ul className="mt-8 max-w-3xl space-y-3 border-l border-brand pl-5 text-ink-2">
              <li><span className="text-ink">Apartments rented.</span> {RULES.occupancy.explain}</li>
              <li><span className="text-ink">Repairs done on time.</span> {RULES.repairsOnTime.explain}</li>
              <li>Unpaid rent and leases ending soon show their size and trend instead of a verdict, because a fair threshold depends on the size of the portfolio.</li>
            </ul>
          )}
          <div className="mt-14 grid gap-x-12 gap-y-14 sm:grid-cols-2 lg:grid-cols-4">
            <Figure title={PLAIN.occupancy.label} term={PLAIN.occupancy.term} value={occRate}
                    format={(v) => pct(v)} help={PLAIN.occupancy.help}
                    detail={`${occupied.toLocaleString()} of ${units.toLocaleString()} apartments`}
                    status={judge(occRate, RULES.occupancy)} rule={RULES.occupancy.explain} />
            <Figure title={PLAIN.delinquent.label} term={PLAIN.delinquent.term} value={owed}
                    format={moneyCompact} help={PLAIN.delinquent.help}
                    detail={facts ? `${facts.delinquency.change <= 0 ? '↓ down' : '↑ up'} ${money(Math.abs(facts.delinquency.change))} from last week` : 'owed by current tenants'} />
            <Figure title={PLAIN.expiring.label} term={PLAIN.expiring.term} value={ending}
                    format={(v) => Math.round(v).toLocaleString()} help={PLAIN.expiring.help}
                    detail={`${moneyCompact(atStake)} of monthly rent up for renewal`} />
            <Figure title={PLAIN.repairs.label} term={PLAIN.repairs.term} value={onTime}
                    format={(v) => pct(v)} help={PLAIN.repairs.help}
                    detail={facts ? `${facts.sla.open_breaches} repairs overdue right now` : `${met.toLocaleString()} of ${judged.toLocaleString()} on time`}
                    status={judge(onTime, RULES.repairsOnTime)} rule={RULES.repairsOnTime.explain} />
          </div>
        </section>

        {/* What you can do here: alternating image rows */}
        <section aria-labelledby="do-h" className="pb-[clamp(88px,10vw,140px)]">
          <Reveal><h2 id="do-h" className="text-[clamp(32px,3.4vw,52px)] leading-[1.08] text-ink">What you can do here</h2></Reveal>
          <div className="mt-16 space-y-[clamp(72px,9vw,128px)]">
            <Row image="/images/balconies.jpg" alt="Curved white balconies repeating up an apartment building"
                 label="Dashboard" name="See the numbers" place="The whole portfolio, or one building"
                 facts="Five headline figures · six charts · every chart also as a table"
                 action={<Link to="/dashboard" className="link-line">Open the dashboard</Link>}>
              Rent collected, profit, unpaid rent, leases ending and repairs, for all twenty buildings
              or any one of them. Each number says what it means in everyday words.
            </Row>
            <Row image="/images/lit-window.jpg" alt="A single warm lit window in a dark apartment building at night" flip
                 label="Ask LeaseLens" name="Ask a question" place="In plain English"
                 facts="Reads the data and the documents · shows its sources · can never change anything"
                 action={<button type="button" onClick={openChat} className="link-line">Ask a question</button>}>
              Type a question like "Which buildings have the most unpaid rent?" The AI looks it up
              and links every figure to the exact data or document it came from.
            </Row>
            <Row image="/images/curtains.jpg" alt="Morning light through sheer curtains in a dark room"
                 label="Every Monday" name="Read the weekly summary" place="Sent to the team in Slack"
                 facts="Unpaid rent this week · leases ending soon · overdue repairs"
                 action={<Link to="/digest" className="link-line">Read this week's summary</Link>}>
              A short update on what changed and what needs attention. The AI writes the sentences;
              a checker compares every number with the real data before anything is sent.
            </Row>
          </div>
        </section>
      </div>

      {/* The one light section */}
      <section aria-labelledby="honest-h" className="bg-stone text-stone-ink">
        <div className="mx-auto grid max-w-[1320px] items-center gap-12 px-5 py-[clamp(88px,10vw,140px)] md:grid-cols-[5fr_6fr] md:gap-24 md:px-10">
          <motion.div className="aspect-[3/4] overflow-hidden"
                      initial={{ clipPath: 'inset(100% 0 0 0)' }} whileInView={{ clipPath: 'inset(0% 0 0 0)' }}
                      viewport={{ once: true, margin: '-100px' }} transition={{ duration: 1.1, ease: EASE }}>
            <img src="/images/house-model.jpg" alt="An architect's pale wooden model of a row of houses" loading="lazy"
                 className="h-full w-full object-cover object-[30%_50%]" />
          </motion.div>
          <Reveal delay={0.4}>
            <p className="label text-stone-accent">Our approach</p>
            <h2 id="honest-h" className="mt-5 text-[clamp(36px,4vw,64px)] leading-[1.06]">How the AI is kept honest</h2>
            <ol className="mt-12 space-y-10">
              {[
                ['I.', 'Every number shows its source.', 'Answers link each figure to the exact data or document it came from, and you can open the database query behind it.'],
                ['II.', 'It can only read, never change.', 'The AI has read only access to a limited set of data, enforced by the database itself, and it never sees tenants’ contact details.'],
                ['III.', 'Numbers are checked before sending.', 'Before the weekly summary goes out, a program compares every number the AI wrote with the real data. One mismatch and the AI’s text is withheld.'],
              ].map(([n, title, body]) => (
                <li key={n} className="grid grid-cols-[3.25rem_1fr] gap-4">
                  <span className="display text-2xl text-stone-accent">{n}</span>
                  <span>
                    <span className="display block text-2xl">{title}</span>
                    <span className="mt-2 block text-stone-muted">{body}</span>
                  </span>
                </li>
              ))}
            </ol>
          </Reveal>
        </div>
      </section>

      {/* The largest buildings, as a quiet list */}
      <section aria-labelledby="buildings-h" className="mx-auto max-w-[1320px] px-5 py-[clamp(88px,10vw,140px)] md:px-10">
        <Reveal className="flex flex-wrap items-end justify-between gap-6">
          <h2 id="buildings-h" className="text-[clamp(32px,3.4vw,52px)] leading-[1.08] text-ink">The largest buildings</h2>
          <Link to="/dashboard" className="link-line">See all {rows.length || 20} buildings</Link>
        </Reveal>
        <ul className="mt-12 border-t border-line">
          {largest.map((r) => (
            <li key={r.property_id} className="border-b border-line">
              <Link to={`/properties/${r.property_id}`}
                    className="group grid grid-cols-[1fr_auto] items-baseline gap-4 py-6 md:grid-cols-[2fr_2fr_1fr_1fr]">
                <span className="display text-2xl text-ink transition-colors duration-300 group-hover:text-brand md:text-3xl">{r.property}</span>
                <span className="hidden text-muted md:block">{city.get(r.property_id) ?? ''}</span>
                <span className="hidden text-ink-2 md:block">{r.units} apartments</span>
                <span className="text-right text-ink-2">{pct(r.occupancy)} rented</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto grid max-w-[1320px] gap-10 px-5 py-16 md:grid-cols-[2fr_1fr_1fr] md:px-10">
          <div>
            <span className="display text-xl tracking-[0.28em] text-ink">LEASELENS</span>
            <p className="mt-4 max-w-sm text-sm text-muted">
              A portfolio project. Synthetic data: no real people, companies or properties.
            </p>
          </div>
          <nav aria-label="Footer" className="flex flex-col gap-3 text-sm">
            <Link to="/dashboard" className="text-ink-2 hover:text-brand">Dashboard</Link>
            <Link to="/digest" className="text-ink-2 hover:text-brand">Weekly summary</Link>
            <a href={REPO} className="text-ink-2 hover:text-brand">Source on GitHub</a>
          </nav>
          <p className="text-sm text-muted">
            Photography from Unsplash by Roman, Mohammadreza Charkhgard, Matei C and Ksenia Obukhova.
          </p>
        </div>
      </footer>
    </MotionConfig>
  )
}
