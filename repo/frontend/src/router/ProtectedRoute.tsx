import { type ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { getDashboardRoute } from '@/pages/auth/LoginPage'
import type { Role } from '@/types'

interface ProtectedRouteProps {
  /** If provided, user must have one of these roles; otherwise redirected to their dashboard */
  allowedRoles?: Role[]
  /** Override rendered element (defaults to <Outlet />) */
  children?: ReactNode
}

export function ProtectedRoute({ allowedRoles, children }: ProtectedRouteProps) {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <LoadingSpinner fullPage label="Restoring session…" />

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={getDashboardRoute(user.role)} replace />
  }

  return children ? <>{children}</> : <Outlet />
}
