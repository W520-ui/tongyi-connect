import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, request } from '../http'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

async function captureError(promise: Promise<unknown>) {
  try {
    await promise
  } catch (error) {
    return error
  }
  throw new Error('expected the request to fail')
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('request()', () => {
  it('returns the parsed JSON body and prefixes the API base URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: 'ok', data: [1, 2] }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(request('/v1/catalog/products')).resolves.toEqual({ status: 'ok', data: [1, 2] })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/catalog/products')
  })

  it('turns a FastAPI string detail into the ApiError message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: '尚未配置 AGENT_LLM_API_KEY，无法生成回复' }, 503)),
    )

    const error = await captureError(request('/v1/agent/chat', { method: 'POST', body: '{}' }))
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(503)
    expect((error as ApiError).message).toBe('尚未配置 AGENT_LLM_API_KEY，无法生成回复')
  })

  // Known defect, fixed in frontend-plan F1: FastAPI 422 bodies carry a list in
  // `detail`, which is currently rendered as "[object Object]".
  it.fails('shows a readable message for 422 validation errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: [{ loc: ['body', 'message'], msg: 'Field required', type: 'missing' }] }, 422),
      ),
    )

    const error = await captureError(request('/v1/agent/chat', { method: 'POST', body: '{}' }))
    expect((error as ApiError).message).not.toContain('[object Object]')
  })
})
