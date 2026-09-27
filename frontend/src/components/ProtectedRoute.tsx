import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../api/auth'
import type { Role } from '../api/types'

export function ProtectedRoute({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { user, loading } = useAuth()

  if (loading) {
    return <div className="p-8 text-center text-slate-500">Loading…</div>
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/" replace />
  }
  return children
}
