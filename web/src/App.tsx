import { useState } from 'react'
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { ChatPanel } from './ChatPanel'
import { Dashboard } from './Dashboard'
import { DigestPage } from './DigestPage'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded px-2 py-1 text-sm ${isActive ? 'bg-grid font-medium text-ink' : 'text-ink-2 hover:bg-grid'}`

export function Shell({ children }: { children: React.ReactNode }) {
  const [chatOpen, setChatOpen] = useState(false)
  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between gap-3 border-b border-border bg-surface px-4 py-3 sm:px-6">
        <div className="flex items-center gap-4">
          <span className="text-lg font-semibold">LeaseLens</span>
          <nav aria-label="Main" className="flex gap-1">
            <NavLink to="/" end className={navClass}>Dashboard</NavLink>
            <NavLink to="/digest" className={navClass}>Weekly digest</NavLink>
          </nav>
        </div>
        <button type="button" onClick={() => setChatOpen((v) => !v)} aria-expanded={chatOpen}
                className="rounded-md bg-ink px-3 py-1.5 text-sm text-surface">
          Ask LeaseLens
        </button>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-5 sm:px-6">{children}</main>
      {chatOpen && <ChatPanel onClose={() => setChatOpen(false)} />}
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/properties/:propertyId" element={<Dashboard />} />
          <Route path="/digest" element={<DigestPage />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  )
}
