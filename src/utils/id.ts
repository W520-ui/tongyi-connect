/**
 * A client_message_id for idempotent sends (A.3.2: 1–64 chars of [A-Za-z0-9_-]).
 * crypto.randomUUID only exists in secure contexts, so plain-HTTP deployments
 * fall back to getRandomValues, which is available everywhere.
 */
export function newClientMessageId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}
