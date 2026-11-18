import { useEffect, useMemo, useState } from 'react'
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { ApiGate } from './ApiGate'
import { ChatContext } from './chat'
import { ChatPanel } from './ChatPanel'
import { Dashboard } from './Dashboard'
import { DigestPage } from './DigestPage'
import { Home } from './Home'

const LINKS = [
  { to: '/', label: 'Home', end: true },
  { to: '/dashboard', label: 'Dashboard', end: false },
  { to: '/digest', label: 'Weekly summary', end: false },
]

const navClass = ({ isActive }: { isActive: boolean }) =>
  `label transition-colors duration-300 ${isActive ? 'text-brand' : 'text-ink hover:text-brand'}`

function Wordmark() {
  return <span className="display text-xl tracking-[0.28em] text-ink">LEASELENS</span>
}

/** 88px bar. Transparent over the welcome page's photo hero until you scroll; charcoal with a
 *  hairline elsewhere. Under 768px it collapses to the wordmark and a "Menu" text button. */
function Navbar({ onAsk, chatOpen }: { onAsk: () => void; chatOpen: boolean }) {
  const { pathname } = useLocation()
  const [scrolled, setScrolled] = useState(false)
  const [menuFor, setMenuFor] = useState<string | null>(null) // menu closes on navigation
  const menuOpen = menuFor === pathname
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  const overHero = pathname === '/' && !scrolled && !menuOpen
  return (
    <>
      <header className={`fixed inset-x-0 top-0 z-30 transition-colors duration-500 ${overHero ? 'bg-transparent' : 'border-b border-line bg-page'}`}>
        <div className="mx-auto flex h-[88px] max-w-[1320px] items-center justify-between gap-4 px-5 md:px-10">
          <Link to="/" aria-label="LeaseLens home"><Wordmark /></Link>
          <nav aria-label="Main" className="hidden items-center gap-10 md:flex">
            {LINKS.map((l) => <NavLink key={l.to} to={l.to} end={l.end} className={navClass}>{l.label}</NavLink>)}
            <button type="button" onClick={onAsk} aria-expanded={chatOpen} className="btn btn-sm">Ask LeaseLens</button>
          </nav>
          <button type="button" className="label text-ink md:hidden" aria-expanded={menuOpen}
                  aria-controls="mobile-menu" onClick={() => setMenuFor(menuOpen ? null : pathname)}>
            {menuOpen ? 'Close' : 'Menu'}
          </button>
        </div>
      </header>
      {menuOpen && (
        <div id="mobile-menu" className="fixed inset-0 z-20 flex flex-col bg-page px-6 pt-[120px] md:hidden">
          <nav aria-label="Mobile" className="flex flex-col gap-6">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end}
                       className={({ isActive }) => `display text-4xl ${isActive ? 'text-brand' : 'text-ink'}`}>
                {l.label}
              </NavLink>
            ))}
          </nav>
          <button type="button" className="btn mt-10 self-start" onClick={() => { setMenuFor(null); onAsk() }}>
            Ask LeaseLens
          </button>
        </div>
      )}
    </>
  )
}

export function Shell({ children }: { children: React.ReactNode }) {
  const [chatOpen, setChatOpen] = useState(false)
  const { pathname } = useLocation()
  const chat = useMemo(() => ({ openChat: () => setChatOpen(true) }), [])
  const fullBleed = pathname === '/' // the welcome page runs its hero under the transparent bar
  return (
    <ChatContext.Provider value={chat}>
      <div className="min-h-screen">
        <Navbar onAsk={() => setChatOpen((v) => !v)} chatOpen={chatOpen} />
        <main className={fullBleed ? '' : 'mx-auto max-w-[1320px] px-5 pb-24 pt-[128px] md:px-10'}>{children}</main>
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
