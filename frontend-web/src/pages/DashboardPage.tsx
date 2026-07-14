import { useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fetchSalesSummary, listMedicines } from '../api/pharmacy'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { Medicine, SaleSummary } from '../types/api'

const LOW_STOCK = 10

export function DashboardPage() {
  const { token } = useAuth()
  const [items, setItems] = useState<Medicine[]>([])
  const [expired, setExpired] = useState<Medicine[]>([])
  const [soon, setSoon] = useState<Medicine[]>([])
  const [expiredTotal, setExpiredTotal] = useState(0)
  const [soonTotal, setSoonTotal] = useState(0)
  const [sales, setSales] = useState<SaleSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const [page, summary, expiredPage, soonPage] = await Promise.all([
          listMedicines(token, {
            page: 1,
            limit: 100,
            sort: 'quantity',
            order: 'asc',
          }),
          fetchSalesSummary(token),
          listMedicines(token, {
            page: 1,
            limit: 10,
            expiry: 'expired',
            sort: 'expiry_date',
            order: 'asc',
          }),
          listMedicines(token, {
            page: 1,
            limit: 10,
            expiry: 'soon',
            days: 30,
            sort: 'expiry_date',
            order: 'asc',
          }),
        ])
        if (!cancelled) {
          setItems(page.items)
          setSales(summary)
          setExpired(expiredPage.items)
          setSoon(soonPage.items)
          setExpiredTotal(expiredPage.total)
          setSoonTotal(soonPage.total)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Failed to load dashboard')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token])

  const lowStock = useMemo(() => items.filter((m) => m.quantity <= LOW_STOCK), [items])
  const inventoryValue = useMemo(
    () => items.reduce((sum, m) => sum + m.quantity * m.price, 0),
    [items],
  )
  const chartData = useMemo(
    () =>
      [...items]
        .sort((a, b) => b.quantity - a.quantity)
        .slice(0, 20)
        .map((m) => ({
          name: m.name.length > 14 ? `${m.name.slice(0, 12)}…` : m.name,
          fullName: m.name,
          quantity: m.quantity,
        })),
    [items],
  )

  return (
    <div className="stack">
      <section className="panel stack">
        <div>
          <h1>Dashboard</h1>
          <p className="muted">Stock, sales totals, and expiry alerts.</p>
        </div>
        {error ? <div className="error-box">{error}</div> : null}
        {loading ? <p className="muted">Loading…</p> : null}

        <div className="metric-grid">
          <div className="metric">
            <div className="metric-label">Total SKUs</div>
            <div className="metric-value">{items.length}</div>
          </div>
          <div className="metric">
            <div className="metric-label">Low stock (≤{LOW_STOCK})</div>
            <div className="metric-value warn">{lowStock.length}</div>
          </div>
          <div className="metric">
            <div className="metric-label">Inventory value</div>
            <div className="metric-value">{inventoryValue.toFixed(2)}</div>
          </div>
          <div className="metric">
            <div className="metric-label">Sales (all time)</div>
            <div className="metric-value">{sales ? sales.sale_count : '—'}</div>
          </div>
          <div className="metric">
            <div className="metric-label">Revenue (all time)</div>
            <div className="metric-value">
              {sales ? sales.total_revenue.toFixed(2) : '—'}
            </div>
          </div>
          <div className="metric">
            <div className="metric-label">Today</div>
            <div className="metric-value">
              {sales
                ? `${sales.today_sale_count} · ${sales.today_revenue.toFixed(2)}`
                : '—'}
            </div>
          </div>
          <div className="metric">
            <div className="metric-label">Expired SKUs</div>
            <div className="metric-value warn">{expiredTotal}</div>
          </div>
          <div className="metric">
            <div className="metric-label">Expiring ≤30d</div>
            <div className="metric-value warn">{soonTotal}</div>
          </div>
        </div>
      </section>

      {(expiredTotal > 0 || soonTotal > 0) && (
        <section className="panel stack">
          <h2>Expiry alerts</h2>
          <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Name</th>
                    <th>Qty</th>
                    <th>Expiry</th>
                  </tr>
                </thead>
                <tbody>
                  {expired.map((m) => (
                    <tr key={`e-${m.id}`}>
                      <td>
                        <span className="badge warn">expired</span>
                      </td>
                      <td>{m.name}</td>
                      <td>{m.quantity}</td>
                      <td>{m.expiry_date}</td>
                    </tr>
                  ))}
                  {soon.map((m) => (
                    <tr key={`s-${m.id}`}>
                      <td>
                        <span className="badge warn">soon</span>
                      </td>
                      <td>{m.name}</td>
                      <td>{m.quantity}</td>
                      <td>{m.expiry_date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
        </section>
      )}

      <section className="panel stack">
        <h2>Stock levels</h2>
        {chartData.length === 0 && !loading ? (
          <p className="muted">No medicines yet — add stock in Inventory.</p>
        ) : (
          <div className="chart-frame">
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(19,33,30,0.12)" />
                <XAxis dataKey="name" angle={-28} textAnchor="end" interval={0} height={70} tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(value) => [value as number, 'Qty']}
                  labelFormatter={(_, payload) =>
                    (payload?.[0]?.payload as { fullName?: string } | undefined)?.fullName || ''
                  }
                />
                <Bar dataKey="quantity" fill="#0f7a65" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      {lowStock.length > 0 ? (
        <section className="panel stack">
          <h2>Below threshold</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Qty</th>
                  <th>Dosage</th>
                  <th>Expiry</th>
                </tr>
              </thead>
              <tbody>
                {lowStock.map((m) => (
                  <tr key={m.id}>
                    <td>{m.name}</td>
                    <td>
                      <span className="badge warn">{m.quantity}</span>
                    </td>
                    <td>{m.dosage}</td>
                    <td>{m.expiry_date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  )
}
