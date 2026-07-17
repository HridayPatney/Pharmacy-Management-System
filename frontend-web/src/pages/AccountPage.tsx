import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchMe } from '../api/pharmacy'
import { ApiError } from '../api/client'
import { canManageStaff, useAuth } from '../auth/AuthContext'
import type { User } from '../types/api'

export function AccountPage() {
  const { token, user, logout, refreshUser } = useAuth()
  const [profile, setProfile] = useState<User | null>(user)
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
          <p className="muted">Your signed-in profile for this pharmacy.</p>
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

      {canManageStaff(profile?.role) ? (
        <section className="panel stack">
          <h2>Administration</h2>
          <p className="muted">
            Staff accounts and the audit log live on the Admin dashboard.
          </p>
          <div className="row">
            <Link to="/admin" className="button-link primary">
              Open Admin dashboard
            </Link>
          </div>
        </section>
      ) : null}
    </div>
  )
}
