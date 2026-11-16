// The merchant key (appendix A.0) is a demo placeholder. It is typed in by the
// merchant and kept in this browser only, so it never ends up in the bundle.

export const MERCHANT_KEY_STORAGE = 'tongyi:merchant-key'

export function getMerchantKey(): string {
  try {
    return localStorage.getItem(MERCHANT_KEY_STORAGE)?.trim() ?? ''
  } catch {
    return ''
  }
}

export function setMerchantKey(value: string): void {
  try {
    const key = value.trim()
    if (key) localStorage.setItem(MERCHANT_KEY_STORAGE, key)
    else localStorage.removeItem(MERCHANT_KEY_STORAGE)
  } catch {
    // Storage can be unavailable (private mode); the key then lasts for this request only.
  }
}
