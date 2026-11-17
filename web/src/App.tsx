import { useMemo, useState } from 'react'
import { BrowserRouter, Link, NavLink, Route, Routes } from 'react-router-dom'
import { ApiGate, useApiInfo } from './ApiGate'
import { ChatContext } from './chat'
import { ChatPanel } from './ChatPanel'
import { Dashboard } from './Dashboard'
import { DigestPage } from './DigestPage'
import { Home } from './Home'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-2 py-1 text-sm ${isActive ? 'bg-hero font-medium text-brand' : 'text-ink-2 hover:bg-grid'}`

/** A lens over a house: the product mark (decorative). */
function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="h-7 w-7 text-brand" aria-hidden fill="none" stroke="currentColor"
         strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="13.5" cy="13.5" r="9.5" />
      <path d="M8.5 15.5v-3.5l5-4 5 4v3.5" />
      <path d="M12 15.5v-2.5h3v2.5" />
      <path d="M20.5 20.5 28 28" />
    </svg>
  )
}

export function Shell({ children }: { children: React.ReactNode }) {
  const [chatOpen, setChatOpen] = useState(false)
  const { demo_mode } = useApiInfo()
  const chat = useMemo(() => ({ openChat: () => setChatOpen(true) }), [])
  return (
    <ChatContext.Provider value={chat}>
      <div className="min-h-screen">
        <header className="sticky top-0 z-10 flex items-center justify-between gap-2 border-b border-border bg-surface/95 px-4 py-3 backdrop-blur sm:px-6">
          <div className="flex min-w-0 items-center gap-2 sm:gap-5">
            <Link to="/" className="flex shrink-0 items-center gap-2" aria-label="LeaseLens home">
              <Logo />
              <span className="hidden text-lg font-semibold tracking-tight sm:inline">LeaseLens</span>
            </Link>
            <nav aria-label="Main" className="flex gap-0.5 whitespace-nowrap sm:gap-1">
              <NavLink to="/" end className={navClass}>Home</NavLink>
              <NavLink to="/dashboard" className={navClass}>Dashboard</NavLink>
              <NavLink to="/digest" className={navClass}>
                <span className="sm:hidden">Summary</span><span className="hidden sm:inline">Weekly summary</span>
              </NavLink>
            </nav>
            {demo_mode && (
              <span className="hidden rounded-full border border-border px-2 py-0.5 text-xs text-muted lg:inline"
                    title="Synthetic data. AI answers are rate-limited and capped per day.">
                Public demo · synthetic data
              </span>
            )}
          </div>
          <button type="button" onClick={() => setChatOpen((v) => !v)} aria-expanded={chatOpen}
                  className="shrink-0 whitespace-nowrap rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-brand-fg shadow-sm hover:opacity-90">
            Ask<span className="hidden sm:inline"> LeaseLens</span>
          </button>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">{children}</main>
        {chatOpen && <ChatPanel onClose={() => setChatOpen(false)} />}
      </div>
    </ChatContext.Provider>
  )
}

export default function App() {
  return (
    <ApiGate>
      <BrowserRouter>
        <Shell>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/properties/:propertyId" element={<Dashboard />} />
            <Route path="/digest" element={<DigestPage />} />
          </Routes>
        </Shell>
      </BrowserRouter>
    </ApiGate>
  )
}
