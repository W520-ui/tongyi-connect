import { afterEach, describe, expect, it, vi } from 'vitest'

import { fail, ok, routeFetch } from '@/test/http'

import { request } from '../client'
import { merchantApi, publicApi } from '../endpoints'
import { ApiError } from '../errors'
import { setMerchantKey } from '../merchant-key'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('request', () => {
  it('returns data from the success envelope and builds the query string', async () => {
    const { calls } = routeFetch({ 'GET /handoffs': () => ok({ items: [] }) })
    await expect(merchantApi.handoffs({ status: ['open', 'acknowledged'], limit: 20 })).resolves.toEqual({ items: [] })
    expect(calls[0]?.url).toBe('/api/v1/handoffs?status=open%2Cacknowledged&limit=20')
  })

  it('throws the error envelope as ApiError, keeping validation details', async () => {
    routeFetch({
      'GET /status': () => fail('VALIDATION_ERROR', 422, '请求参数不合法', [{ loc: ['query', 'limit'], msg: 'too big' }]),
    })
    const error = await publicApi.status().catch((failure: unknown) => failure)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ code: 'VALIDATION_ERROR', status: 422, message: '请求参数不合法' })
    expect((error as ApiError).details).toEqual([{ loc: ['query', 'limit'], msg: 'too big' }])
  })

  it('reports a transport failure as NETWORK_ERROR', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(publicApi.products()).rejects.toMatchObject({ code: 'NETWORK_ERROR', status: 0 })
  })

  it('reports a response that never comes as REQUEST_TIMEOUT', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_input: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
          }),
      ),
    )
    await expect(request('/status', { timeoutMs: 10 })).rejects.toMatchObject({ code: 'REQUEST_TIMEOUT' })
  })

  it('rethrows the AbortError when the caller cancels', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_input: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
          }),
      ),
    )
    const controller = new AbortController()
    const pending = request('/status', { signal: controller.signal })
    controller.abort()
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('treats a non-JSON error page as an internal error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<h1>Bad Gateway</h1>', { status: 502 })))
    await expect(publicApi.status()).rejects.toMatchObject({ code: 'INTERNAL_ERROR', status: 502 })
  })

  it('sends X-Merchant-Key on merchant routes only, and only once a key is saved', async () => {
    const { calls } = routeFetch({
      'GET /dashboard/overview': () => ok({}),
      'GET /catalog/products': () => ok([]),
    })
    await merchantApi.overview()
    setMerchantKey('  demo-key  ')
    await merchantApi.overview()
    await publicApi.products()
    expect(calls.map((call) => call.headers['X-Merchant-Key'])).toEqual([undefined, 'demo-key', undefined])
  })
})
