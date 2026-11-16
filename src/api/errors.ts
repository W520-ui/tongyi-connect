// Error codes from the API contract (appendix A.5) plus the ones the browser raises itself.

export type ServerErrorCode =
  | 'VALIDATION_ERROR'
  | 'UNAUTHORIZED'
  | 'RATE_LIMITED'
  | 'CONVERSATION_NOT_FOUND'
  | 'HANDOFF_NOT_FOUND'
  | 'INVALID_STATE'
  | 'CONVERSATION_BUSY'
  | 'LLM_NOT_CONFIGURED'
  | 'LLM_TIMEOUT'
  | 'AGENT_RUN_TIMEOUT'
  | 'LLM_UPSTREAM_ERROR'
  | 'LLM_BAD_RESPONSE'
  | 'INTERNAL_ERROR'

export type ClientErrorCode =
  | 'NETWORK_ERROR' // the request never reached the backend
  | 'REQUEST_TIMEOUT' // no response within the client-side timeout
  | 'STREAM_STALLED' // the event stream sent nothing (not even a heartbeat) for too long
  | 'STREAM_INTERRUPTED' // the event stream ended before the reply was complete
  | 'BAD_RESPONSE' // the response could not be understood

// Unknown codes from a newer backend are kept as plain strings.
export type ErrorCode = ServerErrorCode | ClientErrorCode | (string & {})

export interface ValidationIssue {
  loc: Array<string | number>
  msg: string
}

const CLIENT_MESSAGES: Record<ClientErrorCode, string> = {
  NETWORK_ERROR: '无法连接后端服务，请检查网络或确认后端已启动',
  REQUEST_TIMEOUT: '请求超时，请稍后重试',
  STREAM_STALLED: '长时间没有收到回复，连接已中止',
  STREAM_INTERRUPTED: '回复中途中断，请重试',
  BAD_RESPONSE: '后端返回的数据无法解析',
}

// Retrying these can succeed without changing the request. Sending the same
// client_message_id again is safe: the backend replays a finished result.
const RETRYABLE = new Set<string>([
  'NETWORK_ERROR',
  'REQUEST_TIMEOUT',
  'STREAM_STALLED',
  'STREAM_INTERRUPTED',
  'RATE_LIMITED',
  'CONVERSATION_BUSY',
  'LLM_TIMEOUT',
  'AGENT_RUN_TIMEOUT',
  'LLM_UPSTREAM_ERROR',
  'LLM_BAD_RESPONSE',
  'INTERNAL_ERROR',
])

export class ApiError extends Error {
  readonly code: ErrorCode
  /** HTTP status; 0 when no response arrived. */
  readonly status: number
  /** Field-level problems for VALIDATION_ERROR, otherwise null. */
  readonly details: ValidationIssue[] | null

  constructor(code: ErrorCode, message?: string, status = 0, details: ValidationIssue[] | null = null) {
    super(message || CLIENT_MESSAGES[code as ClientErrorCode] || '请求失败，请稍后重试')
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }

  get retryable(): boolean {
    return RETRYABLE.has(this.code)
  }
}

export function isApiError(error: unknown, code?: ErrorCode): error is ApiError {
  return error instanceof ApiError && (code === undefined || error.code === code)
}

/** True when the caller cancelled the request (component unmounted, conversation reset…). */
export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

/** Normalizes anything thrown by the API layer into an ApiError. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  return new ApiError('BAD_RESPONSE', error instanceof Error ? error.message : undefined)
}
