import type { EngineInterface, Register, SessionRateLimit } from 'claude-code'

// Under the user's home, not the repo: the installed copy of this mod runs from Claude Code's
// plugin cache, and every session on this laptop writes the same file.
const FILE = '.claude/usage-widget/usage.json'

export type Reading = { percent: number; resetsAt: string | null }

export function readingOf(limits: readonly SessionRateLimit[], kind: string): Reading | null {
  const limit = limits.find(l => l.kind === kind)
  return limit ? { percent: limit.percentUsed, resetsAt: limit.resetsAt ?? null } : null
}

async function writeUsage($: EngineInterface, limits: readonly SessionRateLimit[]) {
  const fiveHour = readingOf(limits, 'five_hour')
  const sevenDay = readingOf(limits, 'seven_day')
  if (!fiveHour && !sevenDay) return
  // Windows has no HOME unless something sets it.
  const home = (await $.env.get('USERPROFILE')) ?? (await $.env.get('HOME'))
  if (!home) return
  const measuredAt = new Date(await $.clock.now()).toISOString()
  await $.fs.write(`${home}/${FILE}`, `${JSON.stringify({ measuredAt, fiveHour, sevenDay })}\n`)
}

export const register: Register = on => {
  // A window's reading arrives with each reply; the event fires when one moves a whole point.
  on('session.measure', async ($, e, next) => {
    if (e.changed.includes('rateLimits')) {
      await writeUsage($, e.rateLimits).catch(err => $.ui.log(`usage-file: ${String(err)}`, { to: 'debug' }))
    }
    return next(e)
  })
}
