import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { fetchMe, login as apiLogin, logoutSession, refreshSession } from '../api/pharmacy'
import { getAccessToken, setAccessToken, subscribeAccessToken } from './tokenStore'
import type { User } from '../types/api'

const LEGACY_TOKEN_KEY = 'pharmaassist_token'

interface AuthState {
  token: string | null
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const logout = useCallback(() => {
    void logoutSession().catch(() => {
      /* cookie may already be gone */
    })
    setAccessToken(null)
    setToken(null)
    setUser(null)
  }, [])

  const refreshUser = useCallback(async () => {
    const bearer = getAccessToken()
    if (!bearer) {
      setLoading(false)
      return
    }
    try {
      const me = await fetchMe(bearer)
      setUser(me)
    } catch {
      logout()
    } finally {
      setLoading(false)
    }
  }, [logout])

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiLogin(email, password)
    setAccessToken(res.access_token)
    setToken(res.access_token)
    setUser(res.user)
  }, [])

  useEffect(() => {
    localStorage.removeItem(LEGACY_TOKEN_KEY)
    return subscribeAccessToken(setToken)
  }, [])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const session = await refreshSession()
        if (cancelled) return
        setToken(session.access_token)
        setUser(session.user)
      } catch {
        if (cancelled || getAccessToken()) return
        setAccessToken(null)
        setToken(null)
        setUser(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const value = useMemo(
    () => ({ token, user, loading, login, logout, refreshUser }),
    [token, user, loading, login, logout, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function canWriteInventory(role: string | undefined): boolean {
  return role === 'admin' || role === 'pharmacist'
}

export function canManageStaff(role: string | undefined): boolean {
  return role === 'admin'
}
