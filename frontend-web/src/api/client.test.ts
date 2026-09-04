import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { setAccessToken } from '../auth/tokenStore'
import { ApiError, apiJson } from './client'

describe('apiJson', () => {
  beforeEach(() => {
    setAccessToken(null)
    vi.stubGlobal('fetch', vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends bearer token and returns JSON', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ access_token: 't', token_type: 'bearer', user: { id: 1 } }),
    })

    const data = await apiJson<{ access_token: string }>('/auth/login', {
      method: 'POST',
      token: 'abc',
      body: JSON.stringify({ email: 'a@b.com', password: 'x' }),
    })

    expect(data.access_token).toBe('t')
    expect(fetchMock).toHaveBeenCalled()
    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers.Authorization).toBe('Bearer abc')
    expect(init.credentials).toBe('include')
  })

  it('refreshes and retries once on 401', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>
    fetchMock
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        json: async () => ({
          error: { code: 'UNAUTHORIZED', message: 'Invalid or expired token' },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          access_token: 'new',
          token_type: 'bearer',
          expires_in: 900,
          user: { id: 1, email: 'a@b.com', role: 'admin', is_active: true, created_at: '' },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items: [] }),
      })

    const data = await apiJson<{ items: unknown[] }>('/inventory/all', { token: 'expired' })
    expect(data.items).toEqual([])
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(String(fetchMock.mock.calls[1][0])).toContain('/auth/refresh')
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe('Bearer new')
  })

  it('parses unified error envelope', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>
    fetchMock.mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      json: async () => ({
        error: { code: 'UNAUTHORIZED', message: 'Not authenticated' },
      }),
    })

    await expect(apiJson('/inventory/all')).rejects.toMatchObject({
      name: 'ApiError',
      status: 401,
      code: 'UNAUTHORIZED',
      message: 'Not authenticated',
    } satisfies Partial<ApiError>)
  })
})
