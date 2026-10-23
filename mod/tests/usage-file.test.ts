import { expect, mock, test } from 'claude-code/testing'

const NOW = Date.parse('2026-10-23T06:02:00Z')
const LIMITS = [
  { kind: 'five_hour', percentUsed: 42.5, resetsAt: '2026-10-23T09:00:00Z' },
  { kind: 'seven_day', percentUsed: 61, resetsAt: '2026-10-24T01:00:00Z' },
]
const CONTEXT = { tokens: 1000, window: 200000, percent: 0.5 }

function setUp(on: Parameters<Parameters<typeof test>[1]>[1], env: Record<string, string>) {
  const writes: { path: string; text: string }[] = []
  mock.clock(on, { now: NOW })
  mock.env(on, env)
  on('fs.write', (_, e) => {
    writes.push(e)
    return { value: undefined }
  })
  on('session.measure', (_, e) => ({ changed: e.changed }))
  return writes
}

test('a rate-limit change writes both windows under USERPROFILE', async ($, on) => {
  const writes = setUp(on, { USERPROFILE: 'C:\\Users\\jack' })
  await $.session.measure({ context: CONTEXT, rateLimits: LIMITS, changed: ['rateLimits'] })

  expect(writes.length).toBe(1)
  // The engine normalizes the path for the OS before the write reaches a hook.
  expect(writes[0]!.path).toMatch(/Users[\\/]jack[\\/]\.claude[\\/]usage-widget[\\/]usage\.json$/)
  expect(JSON.parse(writes[0]!.text)).toEqual({
    measuredAt: '2026-10-23T06:02:00.000Z',
    fiveHour: { percent: 42.5, resetsAt: '2026-10-23T09:00:00Z' },
    sevenDay: { percent: 61, resetsAt: '2026-10-24T01:00:00Z' },
  })
})

test('HOME is used where USERPROFILE is unset', async ($, on) => {
  const writes = setUp(on, { HOME: '/home/jack' })
  await $.session.measure({ context: CONTEXT, rateLimits: LIMITS, changed: ['rateLimits'] })

  expect(writes[0]!.path).toMatch(/home[\\/]jack[\\/]\.claude[\\/]usage-widget[\\/]usage\.json$/)
})

test('a context-only change writes nothing', async ($, on) => {
  const writes = setUp(on, { USERPROFILE: 'C:\\Users\\jack' })
  await $.session.measure({ context: CONTEXT, rateLimits: LIMITS, changed: ['context'] })

  expect(writes.length).toBe(0)
})

test('no readings (off a subscription) writes nothing', async ($, on) => {
  const writes = setUp(on, { USERPROFILE: 'C:\\Users\\jack' })
  await $.session.measure({ context: CONTEXT, rateLimits: [], changed: ['rateLimits'] })

  expect(writes.length).toBe(0)
})

test('one window alone is written with the other as null', async ($, on) => {
  const writes = setUp(on, { USERPROFILE: 'C:\\Users\\jack' })
  await $.session.measure({ context: CONTEXT, rateLimits: [LIMITS[1]!], changed: ['rateLimits'] })

  expect(JSON.parse(writes[0]!.text).fiveHour).toBe(null)
  expect(JSON.parse(writes[0]!.text).sevenDay.percent).toBe(61)
})
