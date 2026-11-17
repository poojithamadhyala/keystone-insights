import { fireEvent, render, screen } from '@testing-library/react'
import { ChartCard } from './components'

const chart = <svg data-testid="chart" />

test('first load shows a placeholder, not empty axes', () => {
  render(<ChartCard title="Occupancy" chart={chart} loading ready={false} />)
  expect(screen.getByText('Loading…')).toBeInTheDocument()
  expect(screen.queryByTestId('chart')).not.toBeInTheDocument()
})

test('errors offer a retry', () => {
  const retry = vi.fn()
  render(<ChartCard title="NOI" chart={chart} ready error="502 Bad Gateway" onRetry={retry} />)
  expect(screen.getByRole('alert')).toHaveTextContent("Couldn't load this: 502 Bad Gateway")
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(retry).toHaveBeenCalledOnce()
})

test('empty data says so and hides the table toggle', () => {
  render(<ChartCard title="Aging" chart={chart} table={<table />} ready empty="No outstanding balances." />)
  expect(screen.getByText('No outstanding balances.')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Table' })).not.toBeInTheDocument()
})

test('chart has a screen-reader summary and a "why this chart" note', () => {
  render(<ChartCard title="Occupancy" chart={chart} ready summary="from 92.2% to 94.4%" about="Line: one measure over time." />)
  expect(screen.getByRole('img', { name: 'Occupancy: from 92.2% to 94.4%' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Why this chart type: Occupancy' }))
  expect(screen.getByText('Line: one measure over time.')).toBeInTheDocument()
})
