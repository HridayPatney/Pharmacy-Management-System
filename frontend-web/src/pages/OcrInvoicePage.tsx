import { useMemo, useState, type FormEvent } from 'react'
import { extractOcr, listMedicines, searchSimilar, sellMedicines } from '../api/pharmacy'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { InvoicePanel } from '../components/InvoicePanel'
import type { Invoice, Medicine, SearchResult } from '../types/api'

interface LineItem {
  name: string
  quantity: number
}

export function OcrInvoicePage() {
  const { token } = useAuth()
  const [patient, setPatient] = useState('')
  const [doctor, setDoctor] = useState('')
  const [clinic, setClinic] = useState('')
  const [lines, setLines] = useState<LineItem[]>([{ name: '', quantity: 1 }])
  const [inventory, setInventory] = useState<Medicine[]>([])
  const [alts, setAlts] = useState<Record<string, SearchResult[]>>({})
  const [invoice, setInvoice] = useState<Invoice | null>(null)
  const [fileKey, setFileKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<string | null>(null)

  const stockByName = useMemo(() => {
    const map = new Map<string, Medicine>()
    for (const m of inventory) map.set(m.name.toLowerCase(), m)
    return map
  }, [inventory])

  async function refreshInventory() {
    if (!token) return
    const data = await listMedicines(token, { page: 1, limit: 100, sort: 'name' })
    setInventory(data.items)
  }

  async function onUpload(file: File | null) {
    if (!token || !file) return
    setBusy(true)
    setError(null)
    setStatus(null)
    try {
      const result = await extractOcr(token, file)
      setPatient(result["Patient's Name"] || '')
      setDoctor(result["Doctor's Name"] || '')
      setClinic(result["Clinic Name"] || '')
      setFileKey(result.file_key || null)
      const meds = result["Medicines Prescribed"] || []
      setLines(meds.length ? meds.map((name) => ({ name, quantity: 1 })) : [{ name: '', quantity: 1 }])
      await refreshInventory()
      setStatus('OCR complete — review medicines below.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'OCR failed')
    } finally {
      setBusy(false)
    }
  }

  async function checkAvailability() {
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      await refreshInventory()
      const nextAlts: Record<string, SearchResult[]> = {}
      for (const line of lines) {
        const name = line.name.trim()
        if (!name) continue
        const stock = stockByName.get(name.toLowerCase())
        if (!stock || stock.quantity < line.quantity) {
          nextAlts[name] = await searchSimilar(token, name, 8)
        }
      }
      setAlts(nextAlts)
      setStatus('Availability checked.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Availability check failed')
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
    try {
      const res = await sellMedicines(token, medicines, { patient, doctor, clinic })
      setInvoice(res.invoice)
      setStatus(
        res.invoice.sale_id
          ? `Sale #${res.invoice.sale_id} recorded.`
          : 'Sale recorded.',
      )
      await refreshInventory()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sell failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <section className="panel stack">
        <div>
          <h1>OCR & Invoice</h1>
          <p className="muted">
            Extract a prescription, check stock / alternatives, then sell and generate an invoice.
          </p>
        </div>
        {error ? <div className="error-box">{error}</div> : null}
        {status ? <p className="muted">{status}</p> : null}
        {fileKey ? <p className="muted">Stored file key: {fileKey}</p> : null}

        <label>
          Prescription image
          <input
            type="file"
            accept="image/*"
            onChange={(e) => void onUpload(e.target.files?.[0] || null)}
            disabled={busy}
          />
        </label>

        <div className="row">
          <label style={{ flex: 1 }}>
            Patient
            <input value={patient} onChange={(e) => setPatient(e.target.value)} />
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
        <h2>Medicines</h2>
        {lines.map((line, idx) => {
          const stock = stockByName.get(line.name.trim().toLowerCase())
          return (
            <div className="row" key={idx}>
              <label style={{ flex: 2 }}>
                Name
                <input
                  value={line.name}
                  onChange={(e) => {
                    const next = [...lines]
                    next[idx] = { ...line, name: e.target.value }
                    setLines(next)
                  }}
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
                      stock {stock.quantity}
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
        <div className="row">
          <button
            type="button"
            className="ghost"
            onClick={() => setLines([...lines, { name: '', quantity: 1 }])}
          >
            Add line
          </button>
          <button type="button" className="ghost" onClick={() => void checkAvailability()} disabled={busy}>
            Check availability
          </button>
          <button type="button" className="primary" onClick={(e) => void onSell(e)} disabled={busy}>
            Sell & invoice
          </button>
        </div>

        {Object.keys(alts).length > 0 ? (
          <div className="stack">
            <h2>Alternatives</h2>
            {Object.entries(alts).map(([name, results]) => (
              <div key={name}>
                <strong>{name}</strong>
                <ul>
                  {results.map((r) => (
                    <li key={r.name}>
                      {r.name}{' '}
                      <button
                        type="button"
                        className="ghost"
                        onClick={() =>
                          setLines((prev) =>
                            prev.map((l) => (l.name.trim() === name ? { ...l, name: r.name } : l)),
                          )
                        }
                      >
                        Use
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      {invoice ? (
        <InvoicePanel
          invoice={invoice}
          meta={{ patient, doctor, clinic }}
          title={invoice.sale_id ? `Invoice · sale #${invoice.sale_id}` : 'Invoice'}
        />
      ) : null}
    </div>
  )
}
