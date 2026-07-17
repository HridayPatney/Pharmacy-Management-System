import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { listMedicines, sellMedicines } from './pharmacy'

describe('pharmacy API helpers', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('lists inventory with pagination query params', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], page: 1, limit: 10, total: 0 }),
    })

    await listMedicines('tok', { page: 2, limit: 10, q: 'asp', low_stock: 10, sort: 'name', order: 'asc' })

    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/inventory/?')
    expect(String(url)).toContain('page=2')
    expect(String(url)).toContain('q=asp')
    expect(String(url)).toContain('low_stock=10')
    expect(init.headers.Authorization).toBe('Bearer tok')
  })

  it('posts sell payload shape', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        invoice: { items: [], total: 0, timestamp: '2026-01-01 00:00' },
      }),
    })

    await sellMedicines('tok', [{ name: 'Aspirin', quantity: 2 }])
    const [, init] = fetchMock.mock.calls[0]
    expect(JSON.parse(init.body)).toEqual({
      medicines: [{ name: 'Aspirin', quantity: 2 }],
      patient: null,
      doctor: null,
      clinic: null,
      prescription_file_key: null,
    })
  })
})
