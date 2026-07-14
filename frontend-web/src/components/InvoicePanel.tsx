import type { Invoice } from '../types/api'
import { downloadInvoicePdf, type InvoiceMeta } from '../lib/invoicePdf'

interface Props {
  invoice: Invoice
  meta?: InvoiceMeta
  title?: string
}

export function InvoicePanel({ invoice, meta = {}, title = 'Invoice' }: Props) {
  return (
    <section className="panel stack">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>{title}</h2>
          <p className="muted">
            {[meta.patient, meta.doctor, meta.clinic].filter(Boolean).join(' · ') || 'Counter sale'}
            {invoice.timestamp ? ` · ${invoice.timestamp}` : ''}
          </p>
        </div>
        <button
          type="button"
          className="primary"
          onClick={() => downloadInvoicePdf(invoice, meta)}
        >
          Download PDF
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Medicine</th>
              <th>Qty</th>
              <th>Unit</th>
              <th>Subtotal</th>
            </tr>
          </thead>
          <tbody>
            {invoice.items.map((item) => (
              <tr key={`${item.name}-${item.quantity}-${item.unit_price}`}>
                <td>{item.name}</td>
                <td>{item.quantity}</td>
                <td>{item.unit_price.toFixed(2)}</td>
                <td>{item.subtotal.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>
        <strong>Total: {invoice.total.toFixed(2)}</strong>
      </p>
    </section>
  )
}
