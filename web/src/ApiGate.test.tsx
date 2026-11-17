import { render, screen } from '@testing-library/react'
import { ApiGate, useApiInfo } from './ApiGate'

function Probe() {
  const info = useApiInfo()
  return <p>ready demo={String(info.demo_mode)} send={String(info.send_enabled)}</p>
}

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

test('renders the app once /health answers, passing demo flags down', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{"status":"ok","demo_mode":true,"send_enabled":false}', { headers: { 'Content-Type': 'application/json' } })))
  render(<ApiGate><Probe /></ApiGate>)
  expect(await screen.findByText('ready demo=true send=false')).toBeInTheDocument()
})

test('shows the wake-up message while the API is asleep, then recovers', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  let calls = 0
  vi.stubGlobal('fetch', vi.fn(async () => {
    calls += 1
    if (calls < 3) throw new TypeError('Failed to fetch')
    return new Response('{"status":"ok"}', { headers: { 'Content-Type': 'application/json' } })
  }))
  render(<ApiGate><Probe /></ApiGate>)
  await vi.advanceTimersByTimeAsync(5000)
  expect(screen.getByText(/Waking up the demo API/)).toBeInTheDocument()
  await vi.advanceTimersByTimeAsync(5000)
  expect(await screen.findByText('ready demo=false send=true')).toBeInTheDocument()
})

test('a production build without VITE_API_URL is a configuration error', async () => {
  const { apiConfigError } = await import('./api')
  expect(apiConfigError({ PROD: true })).toMatch(/without VITE_API_URL/)
  expect(apiConfigError({ PROD: true, VITE_API_URL: 'https://api.example.com' })).toBeNull()
  expect(apiConfigError({ PROD: false })).toBeNull() // dev uses the Vite proxy
})

test('an HTML page answering /health is reported, not retried forever', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('<!doctype html>', { headers: { 'Content-Type': 'text/html' } })))
  render(<ApiGate><Probe /></ApiGate>)
  expect(await screen.findByText(/serves a web page, not the API/)).toBeInTheDocument()
})
