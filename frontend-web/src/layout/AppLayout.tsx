import { NavLink, Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

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
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="brand">
            Pharma<span>Assist</span>
          </div>
          <div className="user-chip">
            {user.email} · {user.role}
          </div>
        </div>
        <nav className="nav">
          <NavLink to="/inventory" className={({ isActive }) => (isActive ? 'active' : '')}>
            Inventory
          </NavLink>
          <NavLink to="/ocr" className={({ isActive }) => (isActive ? 'active' : '')}>
            OCR & Invoice
          </NavLink>
          <button type="button" className="linkish" onClick={logout}>
            Log out
          </button>
        </nav>
      </header>
      <Outlet />
    </div>
  )
}
