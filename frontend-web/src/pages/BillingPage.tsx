import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { listMedicines, listSales, openPrescription, searchSimilar, sellMedicines, voidSale } from '../api/pharmacy'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { InvoicePanel } from '../components/InvoicePanel'
import { downloadInvoicePdf } from '../lib/invoicePdf'
import type { Invoice, Medicine, Sale, SearchResult } from '../types/api'

interface LineItem {
  name: string
  quantity: number
}

export function BillingPage() {
  const { token } = useAuth()
  const [patient, setPatient] = useState('')
  const [doctor, setDoctor] = useState('')
  const [clinic, setClinic] = useState('')
  const [lines, setLines] = useState<LineItem[]>([{ name: '', quantity: 1 }])
  const [inventory, setInventory] = useState<Medicine[]>([])
  const [alts, setAlts] = useState<Record<string, SearchResult[]>>({})
  const [invoice, setInvoice] = useState<Invoice | null>(null)
  const [history, setHistory] = useState<Sale[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<string | null>(null)

  const stockByName = useMemo(() => {
    const map = new Map<string, Medicine>()
    for (const m of inventory) map.set(m.name.toLowerCase(), m)
    return map
  }, [inventory])

  async function refreshInventory(): Promise<Medicine[]> {
    if (!token) return []
    const data = await listMedicines(token, { page: 1, limit: 100, sort: 'name' })
    setInventory(data.items)
    return data.items
  }

  async function refreshHistory() {
    if (!token) return
    const data = await listSales(token, { page: 1, limit: 25 })
    setHistory(data.items)
    setHistoryTotal(data.total)
  }

  useEffect(() => {
    if (!token) return
    void refreshInventory().catch(() => {
      /* ignore on first load */
    })
    void refreshHistory().catch((err) => {
      setError(err instanceof ApiError ? err.message : 'Failed to load sales history')
    })
  }, [token])

  async function checkAlternatives() {
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      const items = await refreshInventory()
      const map = new Map<string, Medicine>()
      for (const m of items) map.set(m.name.toLowerCase(), m)

      const nextAlts: Record<string, SearchResult[]> = {}
      for (const line of lines) {
        const name = line.name.trim()
        if (!name) continue
        const stock = map.get(name.toLowerCase())
        if (!stock || stock.quantity < line.quantity) {
          try {
            nextAlts[name] = await searchSimilar(token, name, 8)
          } catch (err) {
            nextAlts[name] = []
            if (err instanceof ApiError && err.status !== 404) {
              throw err
            }
          }
        }
      }
      setAlts(nextAlts)
      setStatus(
        Object.keys(nextAlts).length
          ? 'Checked stock — see alternatives below for missing or low items.'
          : 'All lines are in stock.',
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not check alternatives')
    } finally {
      setBusy(false)
    }
  }

  async function onSell(e: FormEvent) {
    e.preventDefault()
    if (!token) return
    const medicines = lines
      .map((l) => ({ name: l.name.trim(), quantity: l.quantity }))
      .filter((l) => l.name && l.quantity > 0)
    if (!medicines.length) {
      setError('Add at least one medicine line.')
      return
    }
    setBusy(true)
    setError(null)
    setStatus(null)
    try {
      await refreshInventory()
      const res = await sellMedicines(token, medicines, { patient, doctor, clinic })
      setInvoice(res.invoice)
      setStatus(
        res.invoice.sale_id
          ? `Sale #${res.invoice.sale_id} recorded — download PDF below.`
          : 'Sale recorded — download PDF below.',
      )
      setLines([{ name: '', quantity: 1 }])
      setAlts({})
      await refreshInventory()
      await refreshHistory()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Billing failed')
    } finally {
      setBusy(false)
    }
  }

  async function onVoid(saleId: number) {
    if (!token) return
    if (!confirm(`Void sale #${saleId}? Stock will be restored.`)) return
    setBusy(true)
    setError(null)
    try {
      await voidSale(token, saleId)
      setStatus(`Sale #${saleId} cancelled and stock restored.`)
      if (invoice?.sale_id === saleId) setInvoice(null)
      await refreshHistory()
      await refreshInventory()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Void failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <section className="panel stack">
        <div>
          <h1>Billing</h1>
          <p className="muted">
            Ring up counter sales, suggest in-stock alternatives when an item is missing, and
            download invoices from sales history.
          </p>
        </div>
        {error ? <div className="error-box">{error}</div> : null}
        {status ? <p className="muted">{status}</p> : null}

        <div className="row">
          <label style={{ flex: 1 }}>
            Patient
            <input value={patient} onChange={(e) => setPatient(e.target.value)} placeholder="Walk-in" />
          </label>
          <label style={{ flex: 1 }}>
            Doctor
            <input value={doctor} onChange={(e) => setDoctor(e.target.value)} />
          </label>
          <label style={{ flex: 1 }}>
            Clinic
            <input value={clinic} onChange={(e) => setClinic(e.target.value)} />
          </label>
        </div>
      </section>

      <section className="panel stack">
        <h2>Sale lines</h2>
        <form className="stack" onSubmit={(e) => void onSell(e)}>
          {lines.map((line, idx) => {
            const stock = stockByName.get(line.name.trim().toLowerCase())
            return (
              <div className="row" key={idx}>
                <label style={{ flex: 2 }}>
                  Medicine
                  <input
                    list="billing-meds"
                    value={line.name}
                    onChange={(e) => {
                      const next = [...lines]
                      next[idx] = { ...line, name: e.target.value }
                      setLines(next)
                    }}
                    onFocus={() => void refreshInventory()}
                  />
                </label>
                <label>
                  Qty
                  <input
                    type="number"
                    min={1}
                    value={line.quantity}
                    onChange={(e) => {
                      const next = [...lines]
                      next[idx] = { ...line, quantity: Number(e.target.value) }
                      setLines(next)
                    }}
                  />
                </label>
                <div>
                  {line.name.trim() ? (
                    stock ? (
                      <span className={stock.quantity >= line.quantity ? 'badge ok' : 'badge warn'}>
                        stock {stock.quantity} · {stock.price.toFixed(2)}
                      </span>
                    ) : (
                      <span className="badge warn">not in inventory</span>
                    )
                  ) : null}
                </div>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => setLines(lines.filter((_, i) => i !== idx))}
                >
                  Remove
                </button>
              </div>
            )
          })}
          <datalist id="billing-meds">
            {inventory.map((m) => (
              <option key={m.id} value={m.name} />
            ))}
          </datalist>
          <div className="row">
            <button
              type="button"
              className="ghost"
              onClick={() => setLines([...lines, { name: '', quantity: 1 }])}
            >
              Add line
            </button>
            <button
              type="button"
              className="ghost"
              disabled={busy}
              onClick={() => void checkAlternatives()}
            >
              Find alternatives
            </button>
            <button type="submit" className="primary" disabled={busy}>
              Charge & invoice
            </button>
          </div>
        </form>

        {Object.keys(alts).length > 0 ? (
          <div className="stack">
            <h2>Alternatives</h2>
            {Object.entries(alts).map(([name, results]) => (
              <div key={name}>
                <strong>{name}</strong>
                {results.length === 0 ? (
                  <p className="muted">No other in-stock alternatives found.</p>
                ) : (
                  <ul>
                    {results.map((r) => (
                      <li key={r.name}>
                        {r.name}
                        {r.quantity != null ? ` · stock ${r.quantity}` : ''}{' '}
                        <button
                          type="button"
                          className="ghost"
                          onClick={() =>
                            setLines((prev) =>
                              prev.map((l) =>
                                l.name.trim() === name ? { ...l, name: r.name } : l,
                              ),
                            )
                          }
                        >
                          Use
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        ) : null}
      </section>

      {invoice ? (
        <InvoicePanel
          invoice={invoice}
          meta={{ patient, doctor, clinic }}
          title={invoice.sale_id ? `Invoice · sale #${invoice.sale_id}` : 'Current invoice'}
        />
      ) : null}

      <section className="panel stack">
        <h2>Sales history ({historyTotal})</h2>
        {history.length === 0 ? (
          <p className="muted">No sales recorded yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Patient</th>
                  <th>When</th>
                  <th>Status</th>
                  <th>Total</th>
                  <th>Items</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {history.map((sale) => (
                  <tr key={sale.id}>
                    <td>#{sale.id}</td>
                    <td>{sale.patient_name || 'Walk-in'}</td>
                    <td>{new Date(sale.created_at).toLocaleString()}</td>
                    <td>
                      {sale.status === 'cancelled' ? (
                        <span className="badge warn">cancelled</span>
                      ) : (
                        <span className="badge ok">completed</span>
                      )}
                    </td>
                    <td>{sale.total.toFixed(2)}</td>
                    <td>{sale.items.length}</td>
                    <td className="row">
                      {sale.prescription_file_key ? (
                        <button
                          type="button"
                          className="ghost"
                          disabled={busy}
                          onClick={() =>
                            void openPrescription(token!, sale.prescription_file_key!).catch(
                              (err) =>
                                setError(
                                  err instanceof ApiError
                                    ? err.message
                                    : 'Could not open prescription',
                                ),
                            )
                          }
                        >
                          Rx
                        </button>
                      ) : null}
                      <button
                        type="button"
                        className="ghost"
                        onClick={() =>
                          downloadInvoicePdf(
                            {
                              items: sale.items.map((i) => ({
                                name: i.medicine_name,
                                quantity: i.quantity,
                                unit_price: i.unit_price,
                                subtotal: i.subtotal,
                              })),
                              total: sale.total,
                              timestamp: new Date(sale.created_at).toLocaleString(),
                              sale_id: sale.id,
                            },
                            {
                              patient: sale.patient_name || undefined,
                              doctor: sale.doctor_name || undefined,
                              clinic: sale.clinic_name || undefined,
                            },
                            `sale-${sale.id}.pdf`,
                          )
                        }
                      >
                        PDF
                      </button>
                      {sale.status !== 'cancelled' ? (
                        <button
                          type="button"
                          className="danger"
                          disabled={busy}
                          onClick={() => void onVoid(sale.id)}
                        >
                          Void
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
