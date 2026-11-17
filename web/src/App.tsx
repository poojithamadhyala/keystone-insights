import { useState } from 'react'
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { ApiGate, useApiInfo } from './ApiGate'
import { ChatPanel } from './ChatPanel'
import { Dashboard } from './Dashboard'
import { DigestPage } from './DigestPage'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded px-2 py-1 text-sm ${isActive ? 'bg-grid font-medium text-ink' : 'text-ink-2 hover:bg-grid'}`

export function Shell({ children }: { children: React.ReactNode }) {
  const [chatOpen, setChatOpen] = useState(false)
  const { demo_mode } = useApiInfo()
  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between gap-2 border-b border-border bg-surface px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-2 sm:gap-4">
          <span className="text-lg font-semibold">LeaseLens</span>
          <nav aria-label="Main" className="flex gap-1 whitespace-nowrap">
            <NavLink to="/" end className={navClass}>Dashboard</NavLink>
            <NavLink to="/digest" className={navClass}>
              <span className="sm:hidden">Digest</span><span className="hidden sm:inline">Weekly digest</span>
            </NavLink>
          </nav>
          {demo_mode && (
            <span className="hidden rounded border border-border px-2 py-0.5 text-xs text-muted md:inline"
                  title="Synthetic data. AI answers are rate-limited and capped per day.">
              Public demo · synthetic data
            </span>
          )}
        </div>
        <button type="button" onClick={() => setChatOpen((v) => !v)} aria-expanded={chatOpen}
                className="shrink-0 whitespace-nowrap rounded-md bg-ink px-3 py-1.5 text-sm text-surface">
          Ask<span className="hidden sm:inline"> LeaseLens</span>
        </button>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-5 sm:px-6">{children}</main>
      {chatOpen && <ChatPanel onClose={() => setChatOpen(false)} />}
    </div>
  )
}

export default function App() {
  return (
    <ApiGate>
      <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/properties/:propertyId" element={<Dashboard />} />
          <Route path="/digest" element={<DigestPage />} />
        </Routes>
      </Shell>
      </BrowserRouter>
    </ApiGate>
  )
}
