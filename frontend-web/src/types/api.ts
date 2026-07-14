/** Shared API types matching the FastAPI contracts. */

export type Role = 'admin' | 'pharmacist' | 'cashier'

export interface User {
  id: number
  email: string
  role: Role
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Medicine {
  id: string
  name: string
  dosage: string
  quantity: number
  price: number
  expiry_date: string
}

export interface PaginatedMedicines {
  items: Medicine[]
  page: number
  limit: number
  total: number
}

export interface InvoiceItem {
  name: string
  quantity: number
  unit_price: number
  subtotal: number
}

export interface Invoice {
  items: InvoiceItem[]
  total: number
  timestamp: string
}

export interface SellResponse {
  invoice: Invoice
}

export interface SearchResult {
  name: string
  score: number
}

export interface OcrResult {
  "Patient's Name": string | null
  "Medicines Prescribed": string[] | null
  "Doctor's Name": string | null
  "Clinic Name": string | null
  Date: string | null
  file_key?: string
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details?: unknown
  }
}
