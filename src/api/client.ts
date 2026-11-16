import { ApiError, type ValidationIssue } from './errors'
import { getMerchantKey } from './merchant-key'

// Same-origin by default; the Vite dev server proxies /api to FastAPI.
export const API_ROOT = `${(import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')}/v1`

const DEFAULT_TIMEOUT_MS = 15_000

export type Query = Record<string, string | number | null | undefined>

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH'
  body?: unknown
  query?: Query
  headers?: Record<string, string>
  /** Attach the X-Merchant-Key header when the merchant has entered a key. */
  merchant?: boolean
  signal?: AbortSignal
  /** Time allowed until the response headers arrive; 0 disables the timeout. */
  timeoutMs?: number
}

export function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const search = params.toString()
  return `${API_ROOT}${path}${search ? `?${search}` : ''}`
}

/**
 * Low-level fetch: adds headers, a timeout and abort forwarding, and turns
 * transport failures into ApiError. A cancelled request rethrows the AbortError.
 */
export async function send(path: string, options: RequestOptions = {}): Promise<Response> {
  const { method = 'GET', body, query, merchant = false, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = options
  const headers: Record<string, string> = { Accept: 'application/json', ...options.headers }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (merchant) {
    const key = getMerchantKey()
    if (key) headers['X-Merchant-Key'] = key
  }

  const controller = new AbortController()
  // Stays attached after the headers arrive so the caller can still cancel a stream.
  if (signal?.aborted) controller.abort()
  else signal?.addEventListener('abort', () => controller.abort(), { once: true })

  let timedOut = false
  const timer =
    timeoutMs > 0
      ? setTimeout(() => {
          timedOut = true
          controller.abort()
        }, timeoutMs)
      : undefined

  try {
    return await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    })
  } catch (error) {
    if (timedOut) throw new ApiError('REQUEST_TIMEOUT')
    if (signal?.aborted) throw error
    throw new ApiError('NETWORK_ERROR')
  } finally {
    clearTimeout(timer)
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

/** Builds an ApiError from an error envelope (A.5), tolerating FastAPI's bare `{detail}`. */
export function errorFromBody(body: unknown, status: number): ApiError {
  if (isRecord(body) && isRecord(body.error) && typeof body.error.code === 'string') {
    const { code, message, details } = body.error
    return new ApiError(
      code,
      typeof message === 'string' ? message : undefined,
      status,
      Array.isArray(details) ? (details as ValidationIssue[]) : null,
    )
  }
  const detail = isRecord(body) && typeof body.detail === 'string' ? body.detail : undefined
  return new ApiError(status >= 500 ? 'INTERNAL_ERROR' : 'BAD_RESPONSE', detail, status)
}

/** Returns `data` from a success envelope (A.0) or throws the error envelope as ApiError. */
export async function readEnvelope<T>(response: Response): Promise<T> {
  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new ApiError(response.ok ? 'BAD_RESPONSE' : 'INTERNAL_ERROR', undefined, response.status)
  }
  if (response.ok && isRecord(body) && body.status === 'ok' && 'data' in body) return body.data as T
  throw errorFromBody(body, response.status)
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return readEnvelope<T>(await send(path, options))
}
