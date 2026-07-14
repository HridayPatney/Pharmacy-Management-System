import type { ApiErrorBody } from '../types/api'

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

export async function apiJson<T>(
  path: string,
  options: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const { token, headers, ...rest } = options
  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(token),
      ...headers,
    },
  })
  if (!res.ok) await parseError(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export async function apiForm<T>(
  path: string,
  form: FormData,
  token?: string | null,
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: authHeaders(token),
    body: form,
  })
  if (!res.ok) await parseError(res)
  return (await res.json()) as T
}

export function getApiUrl(): string {
  return API_URL
}
