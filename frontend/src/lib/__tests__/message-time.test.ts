import { formatMessageTime } from '../message-time'

const NOW = new Date(2026, 9, 22, 15, 0) // Oct 22 2026, 3:00 PM local
const at = (y: number, m: number, d: number, h: number, min: number) => new Date(y, m, d, h, min).toISOString()

describe('formatMessageTime', () => {
  const time = (iso: string) => new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })

  it('shows only the time for today', () => {
    const iso = at(2026, 9, 22, 9, 5)
    expect(formatMessageTime(iso, NOW)?.label).toBe(time(iso))
  })

  it('says Yesterday for the previous day, even across midnight', () => {
    const iso = at(2026, 9, 21, 23, 59)
    expect(formatMessageTime(iso, NOW)?.label).toBe(`Yesterday, ${time(iso)}`)
  })

  it('adds the date for older messages and the year only when it differs', () => {
    const thisYear = formatMessageTime(at(2026, 8, 3, 10, 0), NOW)!.label
    const lastYear = formatMessageTime(at(2025, 8, 3, 10, 0), NOW)!.label
    expect(thisYear).not.toMatch(/2026/)
    expect(lastYear).toMatch(/2025/)
  })

  it('returns a full date for the tooltip', () => {
    expect(formatMessageTime(at(2026, 9, 22, 9, 5), NOW)!.full).toMatch(/2026/)
  })

  it('ignores missing or invalid timestamps', () => {
    expect(formatMessageTime(undefined, NOW)).toBeNull()
    expect(formatMessageTime('not a date', NOW)).toBeNull()
  })
})
