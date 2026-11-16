import { render, screen } from '@testing-library/react'
import { ApiGate, useApiInfo } from './ApiGate'

function Probe() {
  const info = useApiInfo()
  return <p>ready demo={String(info.demo_mode)} send={String(info.send_enabled)}</p>
}

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

test('renders the app once /health answers, passing demo flags down', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{"status":"ok","demo_mode":true,"send_enabled":false}')))
  render(<ApiGate><Probe /></ApiGate>)
  expect(await screen.findByText('ready demo=true send=false')).toBeInTheDocument()
})

test('shows the wake-up message while the API is asleep, then recovers', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  let calls = 0
  vi.stubGlobal('fetch', vi.fn(async () => {
    calls += 1
    if (calls < 3) throw new TypeError('Failed to fetch')
    return new Response('{"status":"ok"}')
  }))
  render(<ApiGate><Probe /></ApiGate>)
  await vi.advanceTimersByTimeAsync(5000)
  expect(screen.getByText(/Waking up the demo API/)).toBeInTheDocument()
  await vi.advanceTimersByTimeAsync(5000)
  expect(await screen.findByText('ready demo=false send=true')).toBeInTheDocument()
})
