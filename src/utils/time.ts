const relative = new Intl.RelativeTimeFormat('zh-CN', { numeric: 'auto' })

/** Chinese relative time for the merchant console, e.g. "3分钟前". */
export function fromNow(iso: string, now: number = Date.now()): string {
  const time = new Date(iso).getTime()
  if (Number.isNaN(time)) return ''
  const seconds = (time - now) / 1000
  const abs = Math.abs(seconds)
  if (abs < 45) return '刚刚'
  if (abs < 3600) return relative.format(Math.round(seconds / 60), 'minute')
  if (abs < 86_400) return relative.format(Math.round(seconds / 3600), 'hour')
  return relative.format(Math.round(seconds / 86_400), 'day')
}

/** Hour and minute in the given locale, e.g. "14:05". */
export function clockTime(iso: string, locale: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit' }).format(date)
}

export function minutesAgo(minutes: number, now: number = Date.now()): string {
  return new Date(now - minutes * 60_000).toISOString()
}

/** Pulls "5–8" out of catalog text such as "5–8 个工作日" so it can be localized. */
export function dayRange(shippingDays: string): string | null {
  const match = shippingDays.match(/(\d+)\s*[–—-]\s*(\d+)/)
  return match ? `${match[1]}–${match[2]}` : null
}
