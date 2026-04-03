import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Link, useRouteError, isRouteErrorResponse } from 'react-router-dom'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * Class-based error boundary — catches render errors in any child tree.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return <ErrorCard error={this.state.error} onReset={() => this.setState({ error: null })} />
    }
    return this.props.children
  }
}

function ErrorCard({ error, onReset }: { error?: Error; onReset?: () => void }) {
  return (
    <div className="min-h-screen bg-surface-950 flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <div className="bg-surface-900 border border-surface-700/80 rounded-2xl p-8 space-y-6">
          <div className="w-12 h-12 rounded-xl bg-danger-500/10 border border-danger-500/20 flex items-center justify-center">
            <svg className="w-6 h-6 text-danger-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
          </div>

          <div className="space-y-1.5">
            <h2 className="text-base font-semibold text-text-primary">Something went wrong</h2>
            {error?.message && (
              <p className="text-xs text-text-disabled font-mono bg-surface-800 rounded-lg px-3 py-2 break-all">
                {error.message}
              </p>
            )}
          </div>

          <div className="flex gap-3">
            {onReset && (
              <button
                onClick={onReset}
                className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium
                           bg-primary-500/10 text-primary-400 border border-primary-500/20
                           hover:bg-primary-500/20 transition-colors"
              >
                Try again
              </button>
            )}
            <Link
              to="/"
              className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium text-center
                         bg-surface-700/60 text-text-secondary border border-surface-600/60
                         hover:bg-surface-700 transition-colors"
            >
              Go home
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * React Router v6 errorElement — receives router-level errors (404, thrown responses, etc.)
 */
export function RouteErrorPage() {
  const routeError = useRouteError()

  let message = 'An unexpected error occurred.'
  if (isRouteErrorResponse(routeError)) {
    message = routeError.status === 404
      ? 'Page not found.'
      : `${routeError.status} — ${routeError.statusText}`
  } else if (routeError instanceof Error) {
    message = routeError.message
  }

  return <ErrorCard error={new Error(message)} />
}
