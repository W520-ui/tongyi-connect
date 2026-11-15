import { describe, expect, it } from 'vitest'

import { dayRange, fromNow } from '../time'

describe('dayRange', () => {
  it('extracts the numeric range from catalog shipping text', () => {
    expect(dayRange('5–8 个工作日')).toBe('5–8')
    expect(dayRange('7-12 个工作日')).toBe('7–12')
    expect(dayRange('次日达')).toBeNull()
  })
})

describe('fromNow', () => {
  const now = Date.parse('2026-11-14T12:00:00Z')

  it('says 刚刚 within the last 45 seconds', () => {
    expect(fromNow('2026-11-14T11:59:30Z', now)).toBe('刚刚')
  })

  it('formats minutes, hours and days in Chinese', () => {
    expect(fromNow('2026-11-14T11:55:00Z', now)).toBe('5分钟前')
    expect(fromNow('2026-11-14T09:00:00Z', now)).toBe('3小时前')
    expect(fromNow('2026-11-11T12:00:00Z', now)).toBe('3天前')
  })

  it('returns an empty string for invalid input', () => {
    expect(fromNow('not-a-date', now)).toBe('')
  })
})
