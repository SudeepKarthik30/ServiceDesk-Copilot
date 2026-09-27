import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, apiErrorMessage, tokenStore } from './client'
import type { UserBrief } from './types'

interface AuthContextValue {
  user: UserBrief | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserBrief | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!tokenStore.getAccess()) {
      setLoading(false)
      return
    }
    api
      .get<UserBrief>('/auth/me/')
      .then((res) => setUser(res.data))
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false))
  }, [])

  async function login(email: string, password: string) {
    try {
      const { data } = await api.post<{ access: string; refresh: string }>('/auth/token/', {
        email,
        password,
      })
      tokenStore.set(data.access, data.refresh)
    } catch (error) {
      throw new Error(apiErrorMessage(error, 'Invalid email or password.'))
    }
    const me = await api.get<UserBrief>('/auth/me/')
    setUser(me.data)
  }

  function logout() {
    tokenStore.clear()
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
