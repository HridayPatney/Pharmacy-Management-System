import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { ApiError, apiJson } from '../api/client'

describe('apiJson', () => {
  beforeEach(() => {
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
