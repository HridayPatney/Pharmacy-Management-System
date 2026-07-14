import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  addMedicine,
  deleteMedicine,
  listMedicines,
  updateMedicine,
} from '../api/pharmacy'
import { ApiError } from '../api/client'
import { canWriteInventory, useAuth } from '../auth/AuthContext'
import type { Medicine } from '../types/api'

const emptyForm: Medicine = {
  id: '',
  name: '',
  dosage: '',
  quantity: 0,
  price: 0,
  expiry_date: '',
}

export function InventoryPage() {
  const { token, user } = useAuth()
  const writable = canWriteInventory(user?.role)

  const [items, setItems] = useState<Medicine[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [limit] = useState(10)
  const [q, setQ] = useState('')
  const [lowStockOnly, setLowStockOnly] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<Medicine>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (!token) return
    setError(null)
    try {
      const data = await listMedicines(token, {
        page,
        limit,
        q: q.trim() || undefined,
        low_stock: lowStockOnly ? 10 : undefined,
        sort: 'name',
        order: 'asc',
      })
      setItems(data.items)
      setTotal(data.total)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load inventory')
    }
  }, [token, page, limit, q, lowStockOnly])

  useEffect(() => {
    void load()
  }, [load])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!token || !writable) return
    setBusy(true)
    setError(null)
    try {
      if (editingId) {
        await updateMedicine(token, editingId, form)
      } else {
        await addMedicine(token, form)
      }
      setForm(emptyForm)
      setEditingId(null)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Save failed')
    } finally {
      setBusy(false)
    }
  }

  async function onDelete(id: string) {
    if (!token || !writable) return
    if (!confirm(`Delete medicine ${id}?`)) return
    setBusy(true)
    try {
      await deleteMedicine(token, id)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Delete failed')
    } finally {
      setBusy(false)
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / limit))

  return (
    <div className="stack">
      <section className="panel stack">
        <div>
          <h1>Inventory</h1>
          <p className="muted">Search, filter low stock, and manage catalog items.</p>
        </div>
        {error ? <div className="error-box">{error}</div> : null}
        <div className="row">
          <label style={{ flex: 1, minWidth: 180 }}>
            Search
            <input
              value={q}
              onChange={(e) => {
                setPage(1)
                setQ(e.target.value)
              }}
              placeholder="Name or ID"
            />
          </label>
          <label>
            <span>Low stock only</span>
            <input
              type="checkbox"
              checked={lowStockOnly}
              onChange={(e) => {
                setPage(1)
                setLowStockOnly(e.target.checked)
              }}
            />
          </label>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Dosage</th>
                <th>Qty</th>
                <th>Price</th>
                <th>Expiry</th>
                {writable ? <th>Actions</th> : null}
              </tr>
            </thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.id}>
                  <td>{m.id}</td>
                  <td>{m.name}</td>
                  <td>{m.dosage}</td>
                  <td>
                    {m.quantity}{' '}
                    {m.quantity <= 10 ? <span className="badge warn">low</span> : null}
                  </td>
                  <td>{m.price.toFixed(2)}</td>
                  <td>{m.expiry_date}</td>
                  {writable ? (
                    <td className="row">
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => {
                          setEditingId(m.id)
                          setForm({ ...m })
                        }}
                      >
                        Edit
                      </button>
                      <button type="button" className="danger" onClick={() => void onDelete(m.id)}>
                        Delete
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))}
              {items.length === 0 ? (
                <tr>
                  <td colSpan={writable ? 7 : 6} className="muted">
                    No medicines found.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <div className="pager">
          <button
            type="button"
            className="ghost"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </button>
          <span className="muted">
            Page {page} / {totalPages} · {total} total
          </span>
          <button
            type="button"
            className="ghost"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      </section>

      {writable ? (
        <section className="panel stack">
          <h2>{editingId ? 'Update medicine' : 'Add medicine'}</h2>
          <form className="stack" onSubmit={onSubmit}>
            <div className="row">
              <label>
                ID
                <input
                  value={form.id}
                  disabled={Boolean(editingId)}
                  onChange={(e) => setForm({ ...form, id: e.target.value })}
                  required
                />
              </label>
              <label>
                Name
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                />
              </label>
              <label>
                Dosage
                <input
                  value={form.dosage}
                  onChange={(e) => setForm({ ...form, dosage: e.target.value })}
                  required
                />
              </label>
              <label>
                Quantity
                <input
                  type="number"
                  min={0}
                  value={form.quantity}
                  onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })}
                  required
                />
              </label>
              <label>
                Price
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.price}
                  onChange={(e) => setForm({ ...form, price: Number(e.target.value) })}
                  required
                />
              </label>
              <label>
                Expiry
                <input
                  type="date"
                  value={form.expiry_date}
                  onChange={(e) => setForm({ ...form, expiry_date: e.target.value })}
                  required
                />
              </label>
            </div>
            <div className="row">
              <button className="primary" type="submit" disabled={busy}>
                {editingId ? 'Save changes' : 'Add medicine'}
              </button>
              {editingId ? (
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    setEditingId(null)
                    setForm(emptyForm)
                  }}
                >
                  Cancel
                </button>
              ) : null}
            </div>
          </form>
        </section>
      ) : (
        <section className="panel">
          <p className="muted">Your role can view and sell stock, but not edit the catalog.</p>
        </section>
      )}
    </div>
  )
}
