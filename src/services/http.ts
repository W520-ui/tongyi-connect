const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly payload: unknown

  constructor(message: string, status: number, payload: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

export interface RequestOptions extends RequestInit {
  timeoutMs?: number
}

function resolveUrl(path: string) {
  if (/^https?:\/\//.test(path)) {
    return path
  }

  return `${apiBaseUrl}/${path.replace(/^\//, '')}`
}

async function readPayload(response: Response) {
  const contentType = response.headers.get('content-type') ?? ''

  if (contentType.includes('application/json')) {
    return response.json()
  }

  return response.text()
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 15_000, headers, signal, ...init } = options
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)

  if (signal) {
    signal.addEventListener('abort', () => controller.abort(), { once: true })
  }

  const requestHeaders = new Headers(headers)
  if (init.body && !(init.body instanceof FormData) && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json')
  }

  try {
    const response = await fetch(resolveUrl(path), {
      ...init,
      headers: requestHeaders,
      signal: controller.signal,
    })
    const payload = await readPayload(response)

    if (!response.ok) {
      const message =
        typeof payload === 'object' && payload !== null
          ? 'message' in payload
            ? String(payload.message)
            : 'detail' in payload
              ? String(payload.detail)
              : 'error' in payload
                ? String(payload.error)
                : `请求失败（${response.status}）`
          : `请求失败（${response.status}）`
      throw new ApiError(message, response.status, payload)
    }

    return payload as T
  } finally {
    window.clearTimeout(timeout)
  }
}
