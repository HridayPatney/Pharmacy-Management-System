import { apiForm, apiJson } from './client'
import type {
  AuditLog,
  Medicine,
  OcrResult,
  PaginatedMedicines,
  PaginatedSales,
  Sale,
  SaleSummary,
  SearchResult,
  SellResponse,
  TokenResponse,
  User,
} from '../types/api'

export function login(email: string, password: string) {
  return apiJson<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export function fetchMe(token: string) {
  return apiJson<User>('/auth/me', { token })
}

export function listMedicines(
  token: string,
  params: {
    page?: number
    limit?: number
    q?: string
    low_stock?: number
    sort?: string
    order?: string
  } = {},
) {
  const qs = new URLSearchParams()
  if (params.page) qs.set('page', String(params.page))
  if (params.limit) qs.set('limit', String(params.limit))
  if (params.q) qs.set('q', params.q)
  if (params.low_stock != null) qs.set('low_stock', String(params.low_stock))
  if (params.sort) qs.set('sort', params.sort)
  if (params.order) qs.set('order', params.order)
  const query = qs.toString()
  return apiJson<PaginatedMedicines>(`/inventory/?${query}`, { token })
}

export function addMedicine(token: string, med: Medicine) {
  return apiJson<Medicine>('/inventory/add', {
    method: 'POST',
    token,
    body: JSON.stringify(med),
  })
}

export function updateMedicine(token: string, id: string, med: Medicine) {
  return apiJson<Medicine>(`/inventory/update/${encodeURIComponent(id)}`, {
    method: 'PUT',
    token,
    body: JSON.stringify(med),
  })
}

export function deleteMedicine(token: string, id: string) {
  return apiJson<{ detail: string }>(`/inventory/delete/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    token,
  })
}

export function sellMedicines(
  token: string,
  medicines: { name: string; quantity: number }[],
  meta: { patient?: string; doctor?: string; clinic?: string } = {},
) {
  return apiJson<SellResponse>('/inventory/sell', {
    method: 'POST',
    token,
    body: JSON.stringify({
      medicines,
      patient: meta.patient || null,
      doctor: meta.doctor || null,
      clinic: meta.clinic || null,
    }),
  })
}

export function listSales(token: string, params: { page?: number; limit?: number } = {}) {
  const qs = new URLSearchParams()
  if (params.page) qs.set('page', String(params.page))
  if (params.limit) qs.set('limit', String(params.limit))
  const query = qs.toString()
  return apiJson<PaginatedSales>(`/sales/?${query}`, { token })
}

export function fetchSale(token: string, saleId: number) {
  return apiJson<Sale>(`/sales/${saleId}`, { token })
}

export function fetchSalesSummary(token: string) {
  return apiJson<SaleSummary>('/sales/summary', { token })
}

export function searchSimilar(token: string, medicine_name: string, top_k = 10) {
  return apiJson<SearchResult[]>('/search/similar', {
    method: 'POST',
    token,
    body: JSON.stringify({ medicine_name, top_k }),
  })
}

export function extractOcr(token: string, file: File) {
  const form = new FormData()
  form.append('file', file)
  return apiForm<OcrResult>('/ocr/extract', form, token)
}

export function healthLive() {
  return apiJson<{ status: string }>('/health/live')
}

export function fetchAudit(token: string, limit = 50) {
  return apiJson<AuditLog[]>(`/auth/audit?limit=${limit}`, { token })
}
