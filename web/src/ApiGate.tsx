import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { API_BASE, API_CONFIG_ERROR } from './api'

export interface ApiInfo { demo_mode: boolean; send_enabled: boolean }
const DEFAULT: ApiInfo = { demo_mode: false, send_enabled: true }
const ApiInfoContext = createContext<ApiInfo>(DEFAULT)
export const useApiInfo = () => useContext(ApiInfoContext)

const RETRY_MS = 4000
const GIVE_UP_MS = 150_000 // Render's free tier cold start is usually under a minute

/** Wait for the API before rendering the app. The demo's free API host sleeps when idle, so the
 *  first visit can take up to a minute. Show that plainly instead of a wall of errors. */
export function ApiGate({ children }: { children: ReactNode }) {
  const [info, setInfo] = useState<ApiInfo | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [failed, setFailed] = useState<string | null>(API_CONFIG_ERROR)

  useEffect(() => {
    if (API_CONFIG_ERROR) return
    let cancelled = false
    const started = Date.now()
    const tick = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000)
    async function poll() {
      while (!cancelled) {
        try {
          const res = await fetch(`${API_BASE}/health`)
          if (res.ok) {
            if (!(res.headers.get('content-type') ?? '').includes('json')) {
              // An HTML page answered: the API URL points at the web app, not the API.
              if (!cancelled) setFailed('The API URL serves a web page, not the API. Check VITE_API_URL.')
              return
            }
            const body = (await res.json()) as Partial<ApiInfo>
            if (!cancelled) setInfo({ ...DEFAULT, ...body })
            return
          }
        } catch { /* asleep or unreachable: retry */ }
        if (Date.now() - started > GIVE_UP_MS) {
          if (!cancelled) setFailed("The demo API isn't responding. Please try again in a few minutes.")
          return
        }
        await new Promise((r) => setTimeout(r, RETRY_MS))
      }
    }
    void poll().finally(() => clearInterval(tick))
    return () => { cancelled = true; clearInterval(tick) }
  }, [])

  if (info) return <ApiInfoContext.Provider value={info}>{children}</ApiInfoContext.Provider>
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="max-w-md rounded-lg border border-border bg-surface p-6 text-center" role="status" aria-live="polite">
        <h1 className="text-lg font-semibold">LeaseLens</h1>
        {failed ? (
          <p className="mt-2 text-sm text-critical">{failed}</p>
        ) : (
          <>
            <p className="mt-2 text-sm text-ink-2">
              {elapsed < 3 ? 'Connecting…' : 'Waking up the demo API. Free hosting sleeps when idle, so this can take up to a minute.'}
            </p>
            {elapsed >= 3 && <p className="mt-1 text-xs text-muted tabular">{elapsed}s</p>}
          </>
        )}
      </div>
    </div>
  )
}
