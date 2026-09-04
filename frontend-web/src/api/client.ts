import type { ApiErrorBody, TokenResponse } from '../types/api'
import { getAccessToken, setAccessToken } from '../auth/tokenStore'

const API_URL =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ||
  'http://127.0.0.1:8001'

export class ApiError extends Error {
  status: number
  code: string
  details?: unknown

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

function authHeaders(token?: string | null): HeadersInit {
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

function isRefreshPath(path: string): boolean {
  return path === '/auth/refresh' || path.startsWith('/auth/refresh?')
}

function shouldSkipRefresh(path: string): boolean {
  return (
    path.startsWith('/auth/login') ||
    isRefreshPath(path) ||
    path.startsWith('/auth/logout')
  )
}

async function parseError(res: Response): Promise<never> {
  let code = 'HTTP_ERROR'
  let message = res.statusText || 'Request failed'
  let details: unknown
  try {
    const body = (await res.json()) as ApiErrorBody | { detail?: string }
    if ('error' in body && body.error) {
      code = body.error.code
      message = body.error.message
      details = body.error.details
    } else if ('detail' in body && typeof body.detail === 'string') {
      message = body.detail
    }
  } catch {
    /* ignore */
  }
  throw new ApiError(res.status, code, message, details)
}

let refreshInFlight: Promise<TokenResponse> | null = null

/** Rotate the httpOnly refresh cookie and store the new access JWT in memory. */
export function requestRefresh(): Promise<TokenResponse> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const res = await fetch(`${API_URL}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
      if (!res.ok) {
        setAccessToken(null)
        await parseError(res)
      }
      const data = (await res.json()) as TokenResponse
      setAccessToken(data.access_token)
      return data
    })().finally(() => {
      refreshInFlight = null
    })
  }
  return refreshInFlight
}

async function parseJsonBody<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

type JsonOptions = RequestInit & {
  token?: string | null
  skipRefresh?: boolean
}

async function maybeRetryAfterRefresh(
  path: string,
  res: Response,
  skipRefresh: boolean | undefined,
  retry: (bearer: string) => Promise<Response>,
): Promise<Response> {
  if (res.status !== 401 || skipRefresh || shouldSkipRefresh(path)) return res
  try {
    const session = await requestRefresh()
    return await retry(session.access_token)
  } catch {
    return res
  }
}

export async function apiJson<T>(path: string, options: JsonOptions = {}): Promise<T> {
  const { token, headers, skipRefresh, ...rest } = options

  const send = (bearer: string | null) =>
    fetch(`${API_URL}${path}`, {
      ...rest,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(bearer),
        ...headers,
      },
    })

  let res = await send(getAccessToken() ?? token ?? null)
  res = await maybeRetryAfterRefresh(path, res, skipRefresh, (bearer) => send(bearer))
  if (!res.ok) await parseError(res)
  return parseJsonBody<T>(res)
}

export async function apiForm<T>(
  path: string,
  form: FormData,
  token?: string | null,
  skipRefresh?: boolean,
): Promise<T> {
  const send = (bearer: string | null) =>
    fetch(`${API_URL}${path}`, {
      method: 'POST',
      credentials: 'include',
      headers: authHeaders(bearer),
      body: form,
    })

  let res = await send(getAccessToken() ?? token ?? null)
  res = await maybeRetryAfterRefresh(path, res, skipRefresh, (bearer) => send(bearer))
  if (!res.ok) await parseError(res)
  return (await res.json()) as T
}

export function getApiUrl(): string {
  return API_URL
}
