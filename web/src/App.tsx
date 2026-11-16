import { useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ChatPanel } from './ChatPanel'
import { Dashboard } from './Dashboard'

export function Shell({ children }: { children: React.ReactNode }) {
  const [chatOpen, setChatOpen] = useState(false)
  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
        <div>
          <span className="text-lg font-semibold">LeaseLens</span>
          <span className="ml-3 hidden text-sm text-muted sm:inline">Portfolio reporting · synthetic data</span>
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
        </Routes>
      </Shell>
    </BrowserRouter>
  )
}
