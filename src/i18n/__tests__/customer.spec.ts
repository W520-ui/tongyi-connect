import { describe, expect, it } from 'vitest'

import { customerStrings } from '../customer'

describe('customerStrings', () => {
  it('defines the same keys for every language', () => {
    const [first, ...rest] = Object.values(customerStrings)
    const keys = Object.keys(first ?? {}).sort()
    expect(keys.length).toBeGreaterThan(0)
    for (const strings of rest) {
      expect(Object.keys(strings).sort()).toEqual(keys)
    }
  })

  it('offers three non-empty suggestions per language', () => {
    for (const strings of Object.values(customerStrings)) {
      expect(strings.suggestions).toHaveLength(3)
      expect(strings.suggestions.every((text) => text.trim().length > 0)).toBe(true)
    }
  })

  it('formats shipping ranges and stock counts per language', () => {
    expect(customerStrings['en-US'].shipsIn('5–8')).toBe('Ships in 5–8 business days')
    expect(customerStrings['es-ES'].inStock(3)).toBe('3 en stock')
    expect(customerStrings['zh-CN'].shipsIn('6–10')).toBe('6–10 个工作日送达')
  })
})
