import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { getDashboardRoute } from '@/pages/auth/LoginPage'

export function NotFoundPage() {
  const { user } = useAuth()
  const home = user ? getDashboardRoute(user.role) : '/login'

  return (
    <div className="min-h-screen bg-surface-900 flex items-center justify-center p-6">
      <div className="text-center max-w-md">
        <p className="text-7xl font-bold text-primary-500 mb-4">404</p>
        <h1 className="text-2xl font-semibold text-text-primary mb-2">Page not found</h1>
        <p className="text-text-muted mb-8">
          The page you requested does not exist or has been moved.
        </p>
        <Link
          to={home}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium transition-colors"
        >
          Go to Dashboard
        </Link>
      </div>
    </div>
  )
}
