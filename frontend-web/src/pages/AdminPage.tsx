import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import {
  fetchAudit,
  listUsers,
  registerUser,
  updateUser,
} from '../api/pharmacy'
import { ApiError } from '../api/client'
import { canManageStaff, useAuth } from '../auth/AuthContext'
import type { AuditLog, Role, User } from '../types/api'

const ACTION_OPTIONS = [
  '',
  'inventory.sell',
  'sale.void',
  'medicine.delete',
  'auth.user.register',
  'auth.user.update',
]

const ROLE_OPTIONS: Role[] = ['cashier', 'pharmacist', 'admin']

type AdminTab = 'staff' | 'audit'

export function AdminPage() {
  const { token, user } = useAuth()
  const [tab, setTab] = useState<AdminTab>('staff')
  const [staff, setStaff] = useState<User[]>([])
  const [audit, setAudit] = useState<AuditLog[]>([])
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('cashier')

  const [action, setAction] = useState('')
  const [userId, setUserId] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const isAdmin = canManageStaff(user?.role)

  const metrics = useMemo(() => {
    const active = staff.filter((s) => s.is_active).length
    const byRole = ROLE_OPTIONS.map((r) => ({
      role: r,
      count: staff.filter((s) => s.role === r).length,
    }))
    return { total: staff.length, active, byRole }
  }, [staff])

  const loadStaff = useCallback(async () => {
    if (!token) return
    const rows = await listUsers(token)
    setStaff(rows)
  }, [token])

  const loadAudit = useCallback(async () => {
    if (!token) return
    const rows = await fetchAudit(token, {
      limit: 80,
      action: action || undefined,
      user_id: userId.trim() ? Number(userId) : undefined,
      date_from: dateFrom ? new Date(`${dateFrom}T00:00:00Z`).toISOString() : undefined,
      date_to: dateTo ? new Date(`${dateTo}T23:59:59Z`).toISOString() : undefined,
    })
    setAudit(rows)
  }, [token, action, userId, dateFrom, dateTo])

  useEffect(() => {
    if (!token || !isAdmin) return
    let cancelled = false
    ;(async () => {
      setBusy(true)
      setError(null)
      try {
        await loadStaff()
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Failed to load staff')
        }
      } finally {
        if (!cancelled) setBusy(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token, isAdmin, loadStaff])

  useEffect(() => {
    if (!token || !isAdmin || tab !== 'audit') return
    void loadAudit().catch((err) => {
      setError(err instanceof ApiError ? err.message : 'Failed to load audit log')
    })
  }, [token, isAdmin, tab, loadAudit])

  if (!isAdmin) {
    return <Navigate to="/account" replace />
  }

  async function onCreateStaff(e: FormEvent) {
    e.preventDefault()
    if (!token) return
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const created = await registerUser(token, {
        email: email.trim(),
        password,
        role,
      })
      setEmail('')
      setPassword('')
      setRole('cashier')
      setNotice(`Created ${created.email} as ${created.role}.`)
      await loadStaff()
      if (tab === 'audit') await loadAudit()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create staff')
    } finally {
      setBusy(false)
    }
  }

  async function onChangeRole(target: User, nextRole: Role) {
    if (!token || target.role === nextRole) return
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await updateUser(token, target.id, { role: nextRole })
      setNotice(`Updated ${target.email} → ${nextRole}.`)
      await loadStaff()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to update role')
    } finally {
      setBusy(false)
    }
  }

  async function onToggleActive(target: User) {
    if (!token) return
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await updateUser(token, target.id, { is_active: !target.is_active })
      setNotice(
        target.is_active
          ? `Deactivated ${target.email}.`
          : `Reactivated ${target.email}.`,
      )
      await loadStaff()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to update status')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <section className="panel stack">
        <div>
          <h1>Admin</h1>
          <p className="muted">Manage staff accounts and review sensitive pharmacy actions.</p>
        </div>

        <div className="metric-grid">
          <div className="metric">
            <div className="metric-label">Staff</div>
            <div className="metric-value">{metrics.total}</div>
          </div>
          <div className="metric">
            <div className="metric-label">Active</div>
            <div className="metric-value">{metrics.active}</div>
          </div>
          {metrics.byRole.map((row) => (
            <div className="metric" key={row.role}>
              <div className="metric-label">{row.role}</div>
              <div className="metric-value">{row.count}</div>
            </div>
          ))}
        </div>

        <div className="tab-row" role="tablist" aria-label="Admin sections">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'staff'}
            className={tab === 'staff' ? 'tab active' : 'tab'}
            onClick={() => setTab('staff')}
          >
            Staff
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'audit'}
            className={tab === 'audit' ? 'tab active' : 'tab'}
            onClick={() => setTab('audit')}
          >
            Audit log
          </button>
        </div>

        {error ? <div className="error-box">{error}</div> : null}
        {notice ? <div className="notice-box">{notice}</div> : null}
      </section>

      {tab === 'staff' ? (
        <>
          <section className="panel stack">
            <div>
              <h2>Add staff</h2>
              <p className="muted">Creates a login for cashier, pharmacist, or admin.</p>
            </div>
            <form className="row" onSubmit={(e) => void onCreateStaff(e)}>
              <label>
                Email
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="staff@pharmacy.com"
                  autoComplete="off"
                />
              </label>
              <label>
                Temporary password
                <input
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="min 8 characters"
                  autoComplete="new-password"
                />
              </label>
              <label>
                Role
                <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
                  {ROLE_OPTIONS.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </label>
              <button type="submit" className="primary" disabled={busy}>
                Create account
              </button>
            </form>
          </section>

          <section className="panel stack">
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2>Staff roster</h2>
                <p className="muted">Change roles or deactivate accounts. Self-deactivation and last-admin removal are blocked.</p>
              </div>
              <button
                type="button"
                className="ghost"
                disabled={busy}
                onClick={() => void loadStaff().catch((err) => setError(err instanceof ApiError ? err.message : 'Refresh failed'))}
              >
                Refresh
              </button>
            </div>

            {busy && staff.length === 0 ? <p className="muted">Loading staff…</p> : null}

            {staff.length === 0 ? (
              <p className="muted">No staff accounts yet.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Status</th>
                      <th>Created</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {staff.map((row) => {
                      const isSelf = row.id === user?.id
                      return (
                        <tr key={row.id}>
                          <td>{row.id}</td>
                          <td>
                            {row.email}
                            {isSelf ? <span className="badge ok" style={{ marginLeft: '0.4rem' }}>you</span> : null}
                          </td>
                          <td>
                            <select
                              value={row.role}
                              disabled={busy}
                              aria-label={`Role for ${row.email}`}
                              onChange={(e) => void onChangeRole(row, e.target.value as Role)}
                            >
                              {ROLE_OPTIONS.map((r) => (
                                <option key={r} value={r}>
                                  {r}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td>
                            {row.is_active ? (
                              <span className="badge ok">active</span>
                            ) : (
                              <span className="badge warn">inactive</span>
                            )}
                          </td>
                          <td>{new Date(row.created_at).toLocaleString()}</td>
                          <td>
                            <button
                              type="button"
                              className={row.is_active ? 'danger' : 'ghost'}
                              disabled={busy || (isSelf && row.is_active)}
                              onClick={() => void onToggleActive(row)}
                            >
                              {row.is_active ? 'Deactivate' : 'Reactivate'}
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : (
        <section className="panel stack">
          <h2>Audit log</h2>
          <p className="muted">Filter by action, user, and date range.</p>
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
                      <td>{row.user_email || `#${row.user_id}`}</td>
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
      )}
    </div>
  )
}
