import { ApiError } from './errors'

export interface SseEvent {
  event: string
  data: string
}

/**
 * Incremental text/event-stream parser (WHATWG HTML, "Parsing an event stream").
 * Lines end with LF or CRLF; comment lines such as the backend's ": ping"
 * heartbeat are skipped; an event is dispatched on the blank line after it.
 */
export class SseParser {
  private buffer = ''
  private event = ''
  private data: string[] = []

  push(chunk: string): SseEvent[] {
    this.buffer += chunk
    const events: SseEvent[] = []
    let end = this.buffer.indexOf('\n')
    while (end !== -1) {
      let line = this.buffer.slice(0, end)
      this.buffer = this.buffer.slice(end + 1)
      if (line.endsWith('\r')) line = line.slice(0, -1)
      const event = this.readLine(line)
      if (event) events.push(event)
      end = this.buffer.indexOf('\n')
    }
    return events
  }

  private readLine(line: string): SseEvent | null {
    if (line === '') return this.dispatch()
    if (line.startsWith(':')) return null
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') this.event = value
    else if (field === 'data') this.data.push(value)
    return null
  }

  private dispatch(): SseEvent | null {
    const event = this.data.length ? { event: this.event || 'message', data: this.data.join('\n') } : null
    this.event = ''
    this.data = []
    return event
  }
}

export interface ReadStreamOptions {
  /** Abort when nothing at all (not even a heartbeat) arrives for this long. */
  idleTimeoutMs?: number
}

/**
 * Reads an event stream to the end and hands each event to `onEvent`.
 * Throws STREAM_STALLED after the idle timeout (A.4 rule 5: the backend sends
 * a heartbeat every 15 s, the frontend gives up after 30 s of silence).
 * An exception thrown by `onEvent` cancels the stream and propagates.
 */
export async function readEventStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: SseEvent) => void,
  { idleTimeoutMs = 30_000 }: ReadStreamOptions = {},
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  const parser = new SseParser()
  let stalled = false
  let timer: ReturnType<typeof setTimeout> | undefined
  const arm = () => {
    clearTimeout(timer)
    timer = setTimeout(() => {
      stalled = true
      void reader.cancel().catch(() => undefined)
    }, idleTimeoutMs)
  }

  try {
    arm()
    for (;;) {
      const { done, value } = await reader.read()
      if (stalled) throw new ApiError('STREAM_STALLED')
      if (done) break
      arm()
      for (const event of parser.push(decoder.decode(value, { stream: true }))) onEvent(event)
    }
    for (const event of parser.push(decoder.decode())) onEvent(event)
  } catch (error) {
    await reader.cancel().catch(() => undefined)
    throw stalled ? new ApiError('STREAM_STALLED') : error
  } finally {
    clearTimeout(timer)
    reader.releaseLock()
  }
}
