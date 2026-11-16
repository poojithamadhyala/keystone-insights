import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Dashboard } from './Dashboard'

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-surface px-6 py-3">
        <span className="text-lg font-semibold">LeaseLens</span>
        <span className="ml-3 text-sm text-muted">Portfolio reporting · synthetic data</span>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-5 sm:px-6">{children}</main>
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
