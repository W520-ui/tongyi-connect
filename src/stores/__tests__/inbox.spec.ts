import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { conversation, fail, ok, routeFetch, ticket } from '@/test/http'

import { useInboxStore } from '../inbox'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.unstubAllGlobals())

function handoffs(open: ReturnType<typeof ticket>[], resolved: ReturnType<typeof ticket>[] = []) {
  return ({ url }: { url: string }) => ok({ items: url.includes('status=resolved') ? resolved : open })
}

const THREAD = {
  'GET /conversations/c1': () => ok(conversation({ status: 'pending_human' })),
  'GET /conversations/c1/messages': () => ok({ items: [], has_more: false }),
}

describe('inbox store', () => {
  it('loads both ticket lists, selects the first open ticket and loads its conversation', async () => {
    const { calls } = routeFetch({ 'GET /handoffs': handoffs([ticket()], [ticket({ id: 't9', status: 'resolved' })]), ...THREAD })
    const inbox = useInboxStore()
    await inbox.refresh()
    expect(inbox.counts).toEqual({ open: 1, acknowledged: 0, resolved: 1 })
    expect(inbox.selectedId).toBe('t1')
    expect(inbox.thread?.conversation.status).toBe('pending_human')
    expect(calls.filter((call) => call.path === '/handoffs').map((call) => call.url)).toEqual([
      '/api/v1/handoffs?status=open%2Cacknowledged&limit=50',
      '/api/v1/handoffs?status=resolved&limit=20',
    ])
  })

  it('acknowledging follows the ticket to the acknowledged tab', async () => {
    routeFetch({
      'GET /handoffs': handoffs([ticket()]),
      'POST /handoffs/t1/acknowledge': () => ok(ticket({ status: 'acknowledged', acknowledged_at: '2026-11-15T08:05:00+00:00' })),
      ...THREAD,
    })
    const inbox = useInboxStore()
    await inbox.refresh()
    await inbox.acknowledge('t1')
    expect(inbox.tab).toBe('acknowledged')
    expect(inbox.selected?.status).toBe('acknowledged')
    expect(inbox.counts).toEqual({ open: 0, acknowledged: 1, resolved: 0 })
    expect(inbox.pendingAction).toBeNull()
  })

  it('resolving moves the ticket to the resolved list', async () => {
    routeFetch({
      'GET /handoffs': handoffs([ticket({ status: 'acknowledged' })]),
      'POST /handoffs/t1/resolve': () => ok(ticket({ status: 'resolved', resolved_at: '2026-11-15T08:09:00+00:00' })),
      ...THREAD,
    })
    const inbox = useInboxStore()
    await inbox.setTab('acknowledged')
    await inbox.refresh()
    await inbox.resolve('t1')
    expect(inbox.tab).toBe('resolved')
    expect(inbox.counts).toEqual({ open: 0, acknowledged: 0, resolved: 1 })
  })

  it('reloads and rethrows when someone else already changed the ticket', async () => {
    const { calls } = routeFetch({
      'GET /handoffs': [handoffs([ticket()]), handoffs([ticket({ status: 'acknowledged' })])],
      'POST /handoffs/t1/acknowledge': () => fail('INVALID_STATE', 409, '当前状态不允许这个操作'),
      ...THREAD,
    })
    const inbox = useInboxStore()
    await inbox.refresh()
    await expect(inbox.acknowledge('t1')).rejects.toMatchObject({ code: 'INVALID_STATE' })
    expect(calls.filter((call) => call.path === '/handoffs').length).toBeGreaterThanOrEqual(3)
    expect(inbox.pendingAction).toBeNull()
  })

  it('keeps the last good list and exposes the error when a refresh fails', async () => {
    routeFetch({ 'GET /handoffs': [handoffs([ticket()]), handoffs([ticket()]), () => fail('UNAUTHORIZED', 401)], ...THREAD })
    const inbox = useInboxStore()
    await inbox.refresh()
    await inbox.refresh()
    expect(inbox.error?.code).toBe('UNAUTHORIZED')
    expect(inbox.counts.open).toBe(1)
  })
})
