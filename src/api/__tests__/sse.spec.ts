import { describe, expect, it } from 'vitest'

import { readEventStream, SseParser, type SseEvent } from '../sse'

function streamOf(parts: Array<{ text: string; delayMs?: number }>): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const part of parts) {
        if (part.delayMs) await new Promise((resolve) => setTimeout(resolve, part.delayMs))
        controller.enqueue(encoder.encode(part.text))
      }
      controller.close()
    },
  })
}

describe('SseParser', () => {
  it('reassembles events split across chunks and skips heartbeat comments', () => {
    const parser = new SseParser()
    expect(parser.push(': ping\n\nevent: del')).toEqual([])
    expect(parser.push('ta\ndata: {"round":0,')).toEqual([])
    expect(parser.push('"text":"Hi"}\n\n')).toEqual([{ event: 'delta', data: '{"round":0,"text":"Hi"}' }])
  })

  it('accepts CRLF line endings and joins multi-line data', () => {
    const parser = new SseParser()
    expect(parser.push('event: note\r\ndata: one\r\ndata: two\r\n\r\n')).toEqual([{ event: 'note', data: 'one\ntwo' }])
  })

  it('defaults the event name and ignores fields it does not know', () => {
    const parser = new SseParser()
    expect(parser.push('id: 7\nretry: 100\ndata:plain\n\n')).toEqual([{ event: 'message', data: 'plain' }])
  })

  it('does not dispatch an event that has no data', () => {
    const parser = new SseParser()
    expect(parser.push('event: empty\n\n')).toEqual([])
  })
})

describe('readEventStream', () => {
  it('delivers every event until the stream ends', async () => {
    const received: SseEvent[] = []
    await readEventStream(
      streamOf([{ text: 'event: a\ndata: 1\n\n' }, { text: 'event: b\ndata: 2\n\n' }]),
      (event) => received.push(event),
    )
    expect(received.map((event) => event.event)).toEqual(['a', 'b'])
  })

  it('gives up with STREAM_STALLED when nothing arrives within the idle timeout', async () => {
    const silent = new ReadableStream<Uint8Array>({ start() {} })
    await expect(readEventStream(silent, () => undefined, { idleTimeoutMs: 20 })).rejects.toMatchObject({
      code: 'STREAM_STALLED',
    })
  })

  it('treats heartbeats as activity, so a slow run is not cut off', async () => {
    const received: SseEvent[] = []
    const parts = [1, 2, 3, 4].map(() => ({ text: ': ping\n\n', delayMs: 15 }))
    await readEventStream(
      streamOf([...parts, { text: 'event: done\ndata: {}\n\n', delayMs: 15 }]),
      (event) => received.push(event),
      { idleTimeoutMs: 40 },
    )
    expect(received).toEqual([{ event: 'done', data: '{}' }])
  })

  it('stops reading and rethrows when the handler throws', async () => {
    await expect(
      readEventStream(streamOf([{ text: 'event: error\ndata: {}\n\n' }, { text: 'event: late\ndata: {}\n\n' }]), () => {
        throw new Error('handler failed')
      }),
    ).rejects.toThrow('handler failed')
  })
})
