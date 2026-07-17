import { NavLink, Navigate, Outlet } from 'react-router-dom'
import { canManageStaff, useAuth } from '../auth/AuthContext'

export function AppLayout() {
  const { user, loading, logout } = useAuth()

  if (loading) {
    return (
      <div className="login-page">
        <div className="panel">Loading session…</div>
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />

  return (
    <div className="dash-layout">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="sidebar-brand">
          Pharma<span>Assist</span>
        </div>

        <nav className="sidebar-nav">
          <NavLink to="/dashboard" className={({ isActive }) => (isActive ? 'active' : '')}>
            Dashboard
          </NavLink>
          <NavLink to="/inventory" className={({ isActive }) => (isActive ? 'active' : '')}>
            Inventory
          </NavLink>
          <NavLink to="/billing" className={({ isActive }) => (isActive ? 'active' : '')}>
            Billing
          </NavLink>
          <NavLink to="/ocr" className={({ isActive }) => (isActive ? 'active' : '')}>
            OCR
          </NavLink>
          <NavLink to="/chat" className={({ isActive }) => (isActive ? 'active' : '')}>
            Chat
          </NavLink>
          {canManageStaff(user.role) ? (
            <NavLink to="/admin" className={({ isActive }) => (isActive ? 'active' : '')}>
              Admin
            </NavLink>
          ) : null}
          <NavLink to="/account" className={({ isActive }) => (isActive ? 'active' : '')}>
            Account
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="avatar" aria-hidden="true">
              {user.email.slice(0, 1).toUpperCase()}
            </div>
            <div>
              <div className="sidebar-user-email">{user.email}</div>
              <div className="sidebar-user-role">{user.role}</div>
            </div>
          </div>

          <button type="button" className="sidebar-logout" onClick={logout}>
            Log out
          </button>
        </div>
      </aside>

      <div className="dash-main">
        <header className="main-topbar">
          <div className="pill">
            {user.role} · <span className="pill-muted">staff</span>
          </div>
        </header>

        <main className="dash-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
