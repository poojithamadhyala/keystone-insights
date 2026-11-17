import { judge, RULES, STATUS_LABEL } from './health'

test('occupancy rule of thumb', () => {
  expect(judge(0.97, RULES.occupancy)).toBe('good')
  expect(judge(0.95, RULES.occupancy)).toBe('good') // boundary counts as healthy
  expect(judge(0.944, RULES.occupancy)).toBe('warn') // today's portfolio
  expect(judge(0.88, RULES.occupancy)).toBe('crit')
})

test('repairs-on-time rule of thumb', () => {
  expect(judge(0.817, RULES.repairsOnTime)).toBe('warn')
  expect(judge(0.79, RULES.repairsOnTime)).toBe('crit')
})

test('no data means no verdict, never a fake one', () => {
  expect(judge(null, RULES.occupancy)).toBeNull()
  expect(judge(Number.NaN, RULES.occupancy)).toBeNull()
})

test('every status has a plain label', () => {
  expect(STATUS_LABEL).toEqual({ good: 'Healthy', warn: 'Keep an eye on', crit: 'Needs attention' })
})
