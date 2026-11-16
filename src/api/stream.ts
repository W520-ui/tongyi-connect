import { errorFromBody, send } from './client'
import { ApiError } from './errors'
import { readEventStream, type ReadStreamOptions } from './sse'
import type {
  AgentWorkflowData,
  AnalysisUpdate,
  DeltaEvent,
  SendMessageRequest,
  StreamErrorEvent,
  ToolFinishedEvent,
  ToolStartedEvent,
} from './types'

export interface StreamHandlers {
  onToolStarted?: (event: ToolStartedEvent) => void
  onToolFinished?: (event: ToolFinishedEvent) => void
  onDelta?: (event: DeltaEvent) => void
  onCompleted?: (data: AgentWorkflowData) => void
  onAnalysis?: (update: AnalysisUpdate) => void
}

export interface StreamOptions extends ReadStreamOptions {
  signal?: AbortSignal
}

// Preflight may wait for an earlier submission of the same message (A.3.2), so
// allow as long as a non-streaming request before the stream starts.
const STREAM_START_TIMEOUT_MS = 70_000

function parsePayload<T>(data: string): T {
  try {
    return JSON.parse(data) as T
  } catch {
    throw new ApiError('BAD_RESPONSE')
  }
}

/**
 * POST /conversations/{id}/messages/stream (A.4). Resolves with the final
 * workflow from `completed` once the stream has ended, which includes the
 * optional `analysis` event. Errors before the stream starts arrive as JSON;
 * later ones as an `error` event. Both are thrown as ApiError.
 */
export async function streamMessage(
  conversationId: string,
  body: SendMessageRequest,
  handlers: StreamHandlers = {},
  { signal, idleTimeoutMs }: StreamOptions = {},
): Promise<AgentWorkflowData> {
  const response = await send(`/conversations/${encodeURIComponent(conversationId)}/messages/stream`, {
    method: 'POST',
    body,
    signal,
    timeoutMs: STREAM_START_TIMEOUT_MS,
    headers: { Accept: 'text/event-stream' },
  })

  const type = response.headers.get('content-type') ?? ''
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    throw errorFromBody(payload, response.status)
  }
  if (!type.includes('text/event-stream') || !response.body) throw new ApiError('BAD_RESPONSE')

  // A holder object, because TypeScript does not track assignments made inside the callback.
  const result: { completed: AgentWorkflowData | null } = { completed: null }
  await readEventStream(
    response.body,
    ({ event, data }) => {
      switch (event) {
        case 'tool_started':
          handlers.onToolStarted?.(parsePayload<ToolStartedEvent>(data))
          break
        case 'tool_finished':
          handlers.onToolFinished?.(parsePayload<ToolFinishedEvent>(data))
          break
        case 'delta':
          handlers.onDelta?.(parsePayload<DeltaEvent>(data))
          break
        case 'completed':
          result.completed = parsePayload<{ data: AgentWorkflowData }>(data).data
          handlers.onCompleted?.(result.completed)
          break
        case 'analysis':
          handlers.onAnalysis?.(parsePayload<AnalysisUpdate>(data))
          break
        case 'error': {
          const failure = parsePayload<StreamErrorEvent>(data)
          throw new ApiError(failure.code, failure.message, response.status)
        }
        default:
          // Unknown events are ignored so a newer backend can add them safely.
          break
      }
    },
    { idleTimeoutMs },
  )

  if (!result.completed) throw new ApiError('STREAM_INTERRUPTED')
  return result.completed
}

/**
 * Text shown while a reply streams in. A.4 rule 4: text from a round that later
 * calls a tool was only a preamble, so a `tool_started` in that round discards
 * it; the text from `completed` replaces everything at the end.
 */
export class ReplyBuffer {
  private round = -1
  text = ''

  delta(round: number, text: string): void {
    if (round !== this.round) {
      this.round = round
      this.text = ''
    }
    this.text += text
  }

  toolStarted(round: number): void {
    if (round === this.round) this.text = ''
  }
}
