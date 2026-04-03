import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { ProtectedRoute } from './ProtectedRoute'
import { AppShell } from '@/components/layout/AppShell'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { ErrorBoundary, RouteErrorPage } from '@/components/ui/ErrorBoundary'
import { LoginPage, getDashboardRoute } from '@/pages/auth/LoginPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { useAuth } from '@/hooks/useAuth'

// ── Lazy-loaded pages ─────────────────────────────────────────────────────────
const InventoryDashboard  = lazy(() => import('@/pages/inventory/InventoryDashboard').then((m) => ({ default: m.InventoryDashboard })))
const ReceiveStockPage    = lazy(() => import('@/pages/inventory/ReceiveStockPage').then((m) => ({ default: m.ReceiveStockPage })))
const IssueStockPage      = lazy(() => import('@/pages/inventory/IssueStockPage').then((m) => ({ default: m.IssueStockPage })))
const TransferPage        = lazy(() => import('@/pages/inventory/TransferPage').then((m) => ({ default: m.TransferPage })))
const CycleCountPage      = lazy(() => import('@/pages/inventory/CycleCountPage').then((m) => ({ default: m.CycleCountPage })))
const InventorySearchPage = lazy(() => import('@/pages/inventory/InventorySearchPage').then((m) => ({ default: m.InventorySearchPage })))
const CrawlingDashboard      = lazy(() => import('@/pages/crawling/CrawlingDashboard').then((m) => ({ default: m.CrawlingDashboard })))
const SourcesPage            = lazy(() => import('@/pages/crawling/SourcesPage').then((m) => ({ default: m.SourcesPage })))
const RuleVersionEditorPage  = lazy(() => import('@/pages/crawling/RuleVersionEditorPage').then((m) => ({ default: m.RuleVersionEditorPage })))
const TaskMonitorPage        = lazy(() => import('@/pages/crawling/TaskMonitorPage').then((m) => ({ default: m.TaskMonitorPage })))
const RequestDebuggerPage    = lazy(() => import('@/pages/crawling/RequestDebuggerPage').then((m) => ({ default: m.RequestDebuggerPage })))
const AdminDashboard        = lazy(() => import('@/pages/admin/AdminDashboard').then((m) => ({ default: m.AdminDashboard })))
const UserManagementPage    = lazy(() => import('@/pages/admin/UserManagementPage').then((m) => ({ default: m.UserManagementPage })))
const AuditLogPage          = lazy(() => import('@/pages/admin/AuditLogPage').then((m) => ({ default: m.AuditLogPage })))
const SystemSettingsPage    = lazy(() => import('@/pages/admin/SystemSettingsPage').then((m) => ({ default: m.SystemSettingsPage })))
const InboxPage           = lazy(() => import('@/pages/notifications/InboxPage').then((m) => ({ default: m.InboxPage })))
const SubscriptionsPage   = lazy(() => import('@/pages/notifications/SubscriptionsPage').then((m) => ({ default: m.SubscriptionsPage })))
const NotFoundPage        = lazy(() => import('@/pages/common/NotFoundPage').then((m) => ({ default: m.NotFoundPage })))

/** Suspense + ErrorBoundary wrapper for every lazy page */
function Lazy({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary>
      <Suspense fallback={<LoadingSpinner fullPage />}>
        {children}
      </Suspense>
    </ErrorBoundary>
  )
}

export const router = createBrowserRouter([
  // ── Public ─────────────────────────────────────────────────────────────────
  { path: '/login',    element: <LoginPage />,    errorElement: <RouteErrorPage /> },
  { path: '/register', element: <RegisterPage />, errorElement: <RouteErrorPage /> },

  // ── Protected root ─────────────────────────────────────────────────────────
  {
    element: <ProtectedRoute />,
    errorElement: <RouteErrorPage />,
    children: [
      // Root redirect → role-appropriate dashboard
      { index: true, element: <AuthenticatedIndex /> },

      // App shell wraps all authenticated pages
      {
        element: <AppShell />,
        errorElement: <RouteErrorPage />,
        children: [
          // ── Inventory (ADMIN + INVENTORY_MANAGER) ──────────────────────────
          {
            path: 'inventory',
            element: <ProtectedRoute allowedRoles={['ADMIN', 'INVENTORY_MANAGER']} />,
            errorElement: <RouteErrorPage />,
            children: [
              { index: true,     element: <Lazy><InventoryDashboard /></Lazy> },
              { path: 'receive', element: <Lazy><ReceiveStockPage /></Lazy> },
              { path: 'issue',   element: <Lazy><IssueStockPage /></Lazy> },
              { path: 'transfer',element: <Lazy><TransferPage /></Lazy> },
              { path: 'cycle',   element: <Lazy><CycleCountPage /></Lazy> },
              { path: 'search',  element: <Lazy><InventorySearchPage /></Lazy> },
            ],
          },

          // ── Crawling (ADMIN + PROCUREMENT_ANALYST) ─────────────────────────
          {
            path: 'crawling',
            element: <ProtectedRoute allowedRoles={['ADMIN', 'PROCUREMENT_ANALYST']} />,
            errorElement: <RouteErrorPage />,
            children: [
              { index: true,       element: <Lazy><CrawlingDashboard /></Lazy> },
              { path: 'sources',   element: <Lazy><SourcesPage /></Lazy> },
              { path: 'rules',     element: <Lazy><RuleVersionEditorPage /></Lazy> },
              { path: 'tasks',     element: <Lazy><TaskMonitorPage /></Lazy> },
              { path: 'debugger',  element: <Lazy><RequestDebuggerPage /></Lazy> },
            ],
          },

          // ── Admin (ADMIN only) ─────────────────────────────────────────────
          {
            path: 'admin',
            element: <ProtectedRoute allowedRoles={['ADMIN']} />,
            errorElement: <RouteErrorPage />,
            children: [
              { index: true,      element: <Lazy><AdminDashboard /></Lazy> },
              { path: 'users',    element: <Lazy><UserManagementPage /></Lazy> },
              { path: 'audit',    element: <Lazy><AuditLogPage /></Lazy> },
              { path: 'settings', element: <Lazy><SystemSettingsPage /></Lazy> },
            ],
          },

          // ── Notifications (all authenticated users) ───────────────────────
          { path: 'notifications',          element: <Lazy><InboxPage /></Lazy> },
          { path: 'notifications/settings', element: <Lazy><SubscriptionsPage /></Lazy> },

          // ── Catch-all ──────────────────────────────────────────────────────
          { path: '*', element: <Lazy><NotFoundPage /></Lazy> },
        ],
      },
    ],
  },
])

/** Redirects the root path to the role-appropriate dashboard. */
function AuthenticatedIndex() {
  const { user } = useAuth()
  if (!user) return null
  return <Navigate to={getDashboardRoute(user.role)} replace />
}
