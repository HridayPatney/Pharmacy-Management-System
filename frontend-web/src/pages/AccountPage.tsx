import { useCallback, useEffect, useState } from 'react'
import { fetchAudit, fetchMe } from '../api/pharmacy'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { AuditLog, User } from '../types/api'

const ACTION_OPTIONS = [
  '',
  'inventory.sell',
  'sale.void',
  'medicine.delete',
]

export function AccountPage() {
  const { token, user, logout, refreshUser } = useAuth()
  const [profile, setProfile] = useState<User | null>(user)
  const [audit, setAudit] = useState<AuditLog[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [action, setAction] = useState('')
  const [userId, setUserId] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const loadAudit = useCallback(async () => {
    if (!token || !profile || profile.role !== 'admin') return
    const rows = await fetchAudit(token, {
      limit: 80,
      action: action || undefined,
      user_id: userId.trim() ? Number(userId) : undefined,
      date_from: dateFrom ? new Date(`${dateFrom}T00:00:00Z`).toISOString() : undefined,
      date_to: dateTo ? new Date(`${dateTo}T23:59:59Z`).toISOString() : undefined,
    })
    setAudit(rows)
  }, [token, profile, action, userId, dateFrom, dateTo])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    ;(async () => {
      setBusy(true)
      setError(null)
      try {
        const me = await fetchMe(token)
        if (!cancelled) setProfile(me)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Failed to load account')
        }
      } finally {
        if (!cancelled) setBusy(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token])

  useEffect(() => {
    if (!profile || profile.role !== 'admin') {
      setAudit([])
      return
    }
    void loadAudit().catch((err) => {
      setError(err instanceof ApiError ? err.message : 'Failed to load audit log')
    })
  }, [profile, loadAudit])

  return (
    <div className="stack">
      <section className="panel stack">
        <div>
          <h1>Account</h1>
          <p className="muted">Signed-in staff profile for this pharmacy session.</p>
        </div>
        {error ? <div className="error-box">{error}</div> : null}
        {busy && !profile ? <p className="muted">Loading…</p> : null}

        {profile ? (
          <div className="profile-grid">
            <div>
              <div className="metric-label">Email</div>
              <div className="profile-value">{profile.email}</div>
            </div>
            <div>
              <div className="metric-label">Role</div>
              <div className="profile-value">
                <span className="badge ok">{profile.role}</span>
              </div>
            </div>
            <div>
              <div className="metric-label">User ID</div>
              <div className="profile-value">{profile.id}</div>
            </div>
            <div>
              <div className="metric-label">Status</div>
              <div className="profile-value">
                {profile.is_active ? (
                  <span className="badge ok">active</span>
                ) : (
                  <span className="badge warn">inactive</span>
                )}
              </div>
            </div>
            <div>
              <div className="metric-label">Created</div>
              <div className="profile-value">{new Date(profile.created_at).toLocaleString()}</div>
            </div>
          </div>
        ) : null}

        <div className="row">
          <button
            type="button"
            className="ghost"
            onClick={() => void refreshUser()}
            disabled={busy}
          >
            Refresh profile
          </button>
          <button type="button" className="danger" onClick={logout}>
            Log out
          </button>
        </div>
      </section>

      {profile?.role === 'admin' ? (
        <section className="panel stack">
          <h2>Audit log</h2>
          <p className="muted">Filter by action, user, and date range (admin only).</p>
          <div className="row">
            <label>
              Action
              <select value={action} onChange={(e) => setAction(e.target.value)}>
                {ACTION_OPTIONS.map((opt) => (
                  <option key={opt || 'all'} value={opt}>
                    {opt || 'All actions'}
                  </option>
                ))}
              </select>
            </label>
            <label>
              User ID
              <input
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="e.g. 1"
              />
            </label>
            <label>
              From
              <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            </label>
            <label>
              To
              <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </label>
            <button type="button" className="ghost" onClick={() => void loadAudit()}>
              Apply
            </button>
          </div>
          {audit.length === 0 ? (
            <p className="muted">No audit entries for these filters.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>User</th>
                    <th>Action</th>
                    <th>Entity</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.map((row) => (
                    <tr key={row.id}>
                      <td>{new Date(row.created_at).toLocaleString()}</td>
                      <td>
                        {row.user_email || `#${row.user_id}`}
                      </td>
                      <td>{row.action}</td>
                      <td>
                        {row.entity_type}
                        {row.entity_id ? ` #${row.entity_id}` : ''}
                      </td>
                      <td>{row.details || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : null}
    </div>
  )
}
