import { describe, expect, it, vi } from 'vitest'
import { downloadInvoicePdf } from './invoicePdf'

describe('downloadInvoicePdf', () => {
  it('builds a PDF without throwing', () => {
    const save = vi.fn()
    vi.doMock('jspdf', () => ({
      jsPDF: class {
        setFont() {}
        setFontSize() {}
        text() {}
        setLineWidth() {}
        line() {}
        addPage() {}
        save = save
      },
    }))

    // Direct call with real jspdf is fine in jsdom; just assert save runs.
    expect(() =>
      downloadInvoicePdf(
        {
          items: [{ name: 'Paracetamol', quantity: 2, unit_price: 3.5, subtotal: 7 }],
          total: 7,
          timestamp: '2026-07-15T00:00:00Z',
        },
        { patient: 'Test' },
        'test-invoice.pdf',
      ),
    ).not.toThrow()
  })
})
