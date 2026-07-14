import { useEffect, useState } from 'react'
import { fetchAudit, fetchMe } from '../api/pharmacy'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { AuditLog, User } from '../types/api'

export function AccountPage() {
  const { token, user, logout, refreshUser } = useAuth()
  const [profile, setProfile] = useState<User | null>(user)
  const [audit, setAudit] = useState<AuditLog[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    ;(async () => {
      setBusy(true)
      setError(null)
      try {
        const me = await fetchMe(token)
        if (!cancelled) setProfile(me)
        if (me.role === 'admin') {
          const rows = await fetchAudit(token, 40)
          if (!cancelled) setAudit(rows)
        } else if (!cancelled) {
          setAudit([])
        }
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
          <h2>Recent audit log</h2>
          <p className="muted">Admin-only trail of sell / inventory actions.</p>
          {audit.length === 0 ? (
            <p className="muted">No audit entries yet.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Action</th>
                    <th>Entity</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.map((row) => (
                    <tr key={row.id}>
                      <td>{new Date(row.created_at).toLocaleString()}</td>
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
