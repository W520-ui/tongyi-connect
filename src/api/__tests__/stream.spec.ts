import { afterEach, describe, expect, it, vi } from 'vitest'

import { fail, frame, routeFetch, sse, workflow } from '@/test/http'

import { ReplyBuffer, streamMessage } from '../stream'

const PATH = 'POST /conversations/c1/messages/stream'

afterEach(() => vi.unstubAllGlobals())

describe('streamMessage', () => {
  it('dispatches events in order and resolves with the completed workflow after analysis', async () => {
    const final = workflow({ reply: 'Ships in 5–8 days.' })
    const { calls } = routeFetch({
      [PATH]: () =>
        sse([
          ': ping\n\n',
          frame('tool_started', { call_id: 'a', round: 0, name: 'catalog_shipping', args: { destination: 'ES' } }),
          frame('tool_finished', { call_id: 'a', round: 0, name: 'catalog_shipping', ok: true, latency_ms: 12, error: null }),
          frame('delta', { round: 1, text: 'Ships in ' }),
          frame('delta', { round: 1, text: '5–8 days.' }),
          frame('completed', { data: final }),
          frame('analysis', { analysis_source: 'llm', intent: 'logistics' }),
        ]),
    })
    const seen: string[] = []
    const result = await streamMessage(
      'c1',
      { content: 'Ship to Spain?', client_message_id: 'id-1' },
      {
        onToolStarted: (event) => seen.push(`tool_started:${event.name}`),
        onToolFinished: (event) => seen.push(`tool_finished:${event.ok}`),
        onDelta: (event) => seen.push(`delta:${event.text}`),
        onCompleted: (data) => seen.push(`completed:${data.reply}`),
        onAnalysis: (update) => seen.push(`analysis:${update.intent}`),
      },
    )
    expect(result).toEqual(final)
    expect(seen).toEqual([
      'tool_started:catalog_shipping',
      'tool_finished:true',
      'delta:Ships in ',
      'delta:5–8 days.',
      'completed:Ships in 5–8 days.',
      'analysis:logistics',
    ])
    expect(calls[0]?.headers.Accept).toBe('text/event-stream')
    expect(calls[0]?.body).toEqual({ content: 'Ship to Spain?', client_message_id: 'id-1' })
  })

  it('throws an error event as ApiError and stops', async () => {
    routeFetch({ [PATH]: () => sse([frame('delta', { round: 0, text: 'Hel' }), frame('error', { code: 'LLM_TIMEOUT', message: '模型请求超时' })]) })
    await expect(streamMessage('c1', { content: 'Hi' })).rejects.toMatchObject({ code: 'LLM_TIMEOUT', message: '模型请求超时' })
  })

  it('throws preflight errors that arrive as JSON (A.4)', async () => {
    routeFetch({ [PATH]: () => fail('LLM_NOT_CONFIGURED', 503) })
    await expect(streamMessage('c1', { content: 'Hi' })).rejects.toMatchObject({ code: 'LLM_NOT_CONFIGURED', status: 503 })
  })

  it('reports STREAM_INTERRUPTED when the stream ends before completed', async () => {
    routeFetch({ [PATH]: () => sse([frame('delta', { round: 0, text: 'Hel' })]) })
    await expect(streamMessage('c1', { content: 'Hi' })).rejects.toMatchObject({ code: 'STREAM_INTERRUPTED' })
  })
})

describe('ReplyBuffer', () => {
  it('drops the preamble of a round that goes on to call a tool (A.4 rule 4)', () => {
    const buffer = new ReplyBuffer()
    buffer.delta(0, 'Let me ')
    buffer.delta(0, 'check.')
    expect(buffer.text).toBe('Let me check.')
    buffer.toolStarted(0)
    expect(buffer.text).toBe('')
    buffer.delta(1, 'It ships in 5–8 days.')
    buffer.toolStarted(0) // a late event from an earlier round changes nothing
    expect(buffer.text).toBe('It ships in 5–8 days.')
  })
})
