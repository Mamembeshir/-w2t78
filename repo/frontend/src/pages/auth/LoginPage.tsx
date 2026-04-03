import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { CubeIcon } from '@/components/ui/icons'
import type { Role } from '@/types'

function getDashboardRoute(role: Role): string {
  switch (role) {
    case 'ADMIN':               return '/admin'
    case 'INVENTORY_MANAGER':   return '/inventory'
    case 'PROCUREMENT_ANALYST': return '/crawling'
  }
}

export function LoginPage() {
  const { login } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (!username.trim()) { setError('Username is required.'); return }
    if (!password)         { setError('Password is required.'); return }

    setLoading(true)
    try {
      await login(username.trim(), password)
      // login() sets user in context; read role from the context after await
      // The navigate happens after state settles on the next tick
      toast.success('Welcome back!')
    } catch {
      setError('Invalid username or password.')
      setLoading(false)
      return
    }

    // Auth context updated — read via a fresh useAuth() call isn't possible here,
    // but AuthContext.login() receives the response and sets user synchronously.
    // Redirect happens via useEffect watching user in ProtectedRoute.
    // We navigate immediately with a temporary redirect; role redirect handled there.
    navigate('/', { replace: true })
  }

  return (
    <div className="min-h-screen bg-surface-900 flex items-center justify-center p-4">
      {/* Background subtle pattern */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(99,102,241,0.06)_0%,_transparent_60%)] pointer-events-none" />

      <div className="relative w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8 gap-3">
          <div className="w-14 h-14 rounded-2xl bg-primary-500/20 border border-primary-500/30 flex items-center justify-center shadow-glow-primary">
            <CubeIcon className="w-8 h-8 text-primary-400" />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-bold text-text-primary">Warehouse Intelligence</h1>
            <p className="text-sm text-text-muted mt-0.5">Sign in to your account</p>
          </div>
        </div>

        {/* Card */}
        <div className="bg-surface-800 border border-surface-700 rounded-2xl shadow-card-lg p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
            <Input
              label="Username"
              type="text"
              value={username}
              onChange={setUsername}
              placeholder="Enter your username"
              autoComplete="username"
              autoFocus
              required
              disabled={loading}
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              placeholder="Enter your password"
              autoComplete="current-password"
              required
              disabled={loading}
            />

            {error && (
              <div className="bg-danger-500/10 border border-danger-500/30 rounded-xl px-4 py-2.5">
                <p className="text-danger-400 text-sm">{error}</p>
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              className="w-full mt-1"
            >
              Sign in
            </Button>
          </form>
        </div>

        {/* Offline badge */}
        <div className="flex items-center justify-center gap-1.5 mt-6">
          <div className="w-1.5 h-1.5 rounded-full bg-success-400" />
          <span className="text-xs text-text-muted">Offline · Local network only</span>
        </div>
      </div>
    </div>
  )
}

export { getDashboardRoute }
