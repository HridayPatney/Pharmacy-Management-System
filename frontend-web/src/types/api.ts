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
  sale_id?: number | null
}

export interface SellResponse {
  invoice: Invoice
}

export interface SaleItem {
  id: number
  medicine_id: string | null
  medicine_name: string
  quantity: number
  unit_price: number
  subtotal: number
}

export interface Sale {
  id: number
  user_id: number
  patient_name: string | null
  doctor_name: string | null
  clinic_name: string | null
  total: number
  status: 'completed' | 'cancelled' | string
  cancelled_at?: string | null
  cancelled_by_user_id?: number | null
  created_at: string
  items: SaleItem[]
}

export interface PaginatedSales {
  items: Sale[]
  page: number
  limit: number
  total: number
}

export interface SaleSummary {
  sale_count: number
  total_revenue: number
  today_sale_count: number
  today_revenue: number
}

export interface SearchResult {
  name: string
  score: number
  quantity?: number | null
}

export interface OcrResult {
  "Patient's Name": string | null
  "Medicines Prescribed": string[] | null
  "Doctor's Name": string | null
  "Clinic Name": string | null
  Date: string | null
  file_key?: string
  warning?: string
}

export interface AuditLog {
  id: number
  user_id: number
  user_email?: string | null
  action: string
  entity_type: string
  entity_id: string | null
  details: string | null
  created_at: string
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details?: unknown
  }
}
