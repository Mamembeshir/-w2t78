import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { useToast } from '@/hooks/useToast'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { extractMessage } from '@/lib/formErrors'

function WarehouseIcon() {
  return (
    <svg viewBox="0 0 40 40" fill="none" className="w-10 h-10">
      <rect width="40" height="40" rx="10" fill="rgb(var(--primary-500) / 0.12)" />
      <path d="M7 17L20 10L33 17V31H7V17Z" stroke="rgb(var(--primary-400))" strokeWidth="1.5" strokeLinejoin="round" />
      <rect x="16" y="22" width="8" height="9" rx="1" stroke="rgb(var(--primary-400))" strokeWidth="1.5" />
      <path d="M7 17H33" stroke="rgb(var(--primary-500) / 0.4)" strokeWidth="1" />
    </svg>
  )
}

export function RegisterPage() {
  const toast = useToast()
  const navigate = useNavigate()

  const [username, setUsername]             = useState('')
  const [password, setPassword]             = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [email, setEmail]                   = useState('')
  const [loading, setLoading]               = useState(false)
  const [error, setError]                   = useState('')

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')

    if (!username.trim())    { setError('Username is required.'); return }
    if (!password)           { setError('Password is required.'); return }
    if (password !== confirmPassword) { setError('Passwords do not match.'); return }

    setLoading(true)
    try {
      await api.post('/api/auth/register/', {
        username: username.trim(),
        password,
        ...(email.trim() ? { email: email.trim() } : {}),
      })
      toast.success('Account created — sign in to get started.')
      navigate('/login', { replace: true })
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 403) {
        setError('Self-registration is disabled. Contact your administrator to create an account.')
      } else {
        setError(extractMessage(err, 'Registration failed. Please check your details.'))
      }
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-950 flex">

      {/* ── Left brand panel (desktop only) ─────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-[420px] xl:w-[480px] flex-col justify-between
                      bg-surface-900 border-r border-surface-600/40 p-12 flex-shrink-0">
        {/* Top wordmark */}
        <div className="flex items-center gap-3">
          <WarehouseIcon />
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.15em] text-text-disabled">
              Warehouse Intel
            </p>
          </div>
        </div>

        {/* Center content */}
        <div className="space-y-6">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary-500">
              Procurement Analyst Portal
            </p>
            <h1 className="text-4xl font-bold text-text-primary leading-[1.15] tracking-tight">
              Crawl smarter.<br />
              Source faster.<br />
              <span className="text-gradient-amber">Stay in control.</span>
            </h1>
          </div>
          <p className="text-text-muted text-base leading-relaxed max-w-xs">
            Create your analyst account to access crawling rules, task monitoring,
            and supplier intelligence — fully offline on your network.
          </p>

          <ul className="space-y-2.5">
            {[
              'Configure crawl sources and rule sets',
              'Monitor tasks with real-time status',
              'Visual request/response debugger',
              'Canary deployments with auto-rollback',
            ].map((f) => (
              <li key={f} className="flex items-start gap-2.5">
                <span className="mt-1 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-primary-500" />
                <span className="text-sm text-text-secondary">{f}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Bottom offline badge */}
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-success-400 flex-shrink-0" />
          <span className="text-xs text-text-muted">Offline · Local network only</span>
        </div>
      </div>

      {/* ── Right form panel ──────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 lg:p-12">
        {/* Mobile-only logo */}
        <div className="lg:hidden mb-10 text-center">
          <div className="inline-flex items-center gap-3 mb-2">
            <WarehouseIcon />
            <span className="text-base font-bold text-text-primary">Warehouse Intel</span>
          </div>
        </div>

        <div className="w-full max-w-sm">
          {/* Heading */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-text-primary tracking-tight">Create account</h2>
            <p className="mt-1.5 text-sm text-text-muted">
              Analyst access · password must be 10+ characters
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
            <Input
              label="Username"
              type="text"
              value={username}
              onChange={setUsername}
              placeholder="your.username"
              autoComplete="username"
              autoFocus
              required
              disabled={loading}
            />

            <Input
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              placeholder="you@example.com"
              autoComplete="email"
              disabled={loading}
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              placeholder="••••••••••"
              autoComplete="new-password"
              required
              disabled={loading}
            />

            <Input
              label="Confirm Password"
              type="password"
              value={confirmPassword}
              onChange={setConfirmPassword}
              placeholder="••••••••••"
              autoComplete="new-password"
              required
              disabled={loading}
            />

            {error && (
              <div className="flex items-start gap-2.5 bg-danger-500/8 border border-danger-500/25
                              rounded-xl px-4 py-3">
                <svg className="w-4 h-4 text-danger-400 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                </svg>
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
              Create account
            </Button>
          </form>

          {/* Sign in link */}
          <p className="mt-6 text-center text-sm text-text-muted">
            Already have an account?{' '}
            <Link to="/login" className="text-primary-400 hover:text-primary-300 font-medium transition-colors">
              Sign in
            </Link>
          </p>

          {/* Mobile offline badge */}
          <div className="lg:hidden flex items-center justify-center gap-2 mt-8">
            <span className="w-1.5 h-1.5 rounded-full bg-success-400" />
            <span className="text-xs text-text-muted">Offline · Local network only</span>
          </div>
        </div>
      </div>
    </div>
  )
}
