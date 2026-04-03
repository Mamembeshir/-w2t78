import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { ProtectedRoute } from './ProtectedRoute'
import { AppShell } from '@/components/layout/AppShell'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { LoginPage, getDashboardRoute } from '@/pages/auth/LoginPage'
import { useAuth } from '@/hooks/useAuth'

// ── Lazy-loaded pages ─────────────────────────────────────────────────────────
const InventoryDashboard  = lazy(() => import('@/pages/inventory/InventoryDashboard').then((m) => ({ default: m.InventoryDashboard })))
const ReceiveStockPage    = lazy(() => import('@/pages/inventory/ReceiveStockPage').then((m) => ({ default: m.ReceiveStockPage })))
const IssueStockPage      = lazy(() => import('@/pages/inventory/IssueStockPage').then((m) => ({ default: m.IssueStockPage })))
const TransferPage        = lazy(() => import('@/pages/inventory/TransferPage').then((m) => ({ default: m.TransferPage })))
const CycleCountPage      = lazy(() => import('@/pages/inventory/CycleCountPage').then((m) => ({ default: m.CycleCountPage })))
const InventorySearchPage = lazy(() => import('@/pages/inventory/InventorySearchPage').then((m) => ({ default: m.InventorySearchPage })))
const CrawlingDashboard   = lazy(() => import('@/pages/crawling/CrawlingDashboard').then((m) => ({ default: m.CrawlingDashboard })))
const AdminDashboard      = lazy(() => import('@/pages/admin/AdminDashboard').then((m) => ({ default: m.AdminDashboard })))
const NotImplementedPage  = lazy(() => import('@/pages/common/NotImplementedPage').then((m) => ({ default: m.NotImplementedPage })))

function Lazy({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<LoadingSpinner fullPage />}>{children}</Suspense>
}

export const router = createBrowserRouter([
  // ── Public ─────────────────────────────────────────────────────────────────
  { path: '/login', element: <LoginPage /> },

  // ── Protected root ─────────────────────────────────────────────────────────
  {
    element: <ProtectedRoute />,
    children: [
      // Root redirect → role-appropriate dashboard (handled by AuthenticatedIndex)
      { index: true, element: <AuthenticatedIndex /> },

      // App shell wraps all authenticated pages
      {
        element: <AppShell />,
        children: [
          // ── Inventory (ADMIN + INVENTORY_MANAGER) ──────────────────────────
          {
            path: 'inventory',
            element: <ProtectedRoute allowedRoles={['ADMIN', 'INVENTORY_MANAGER']} />,
            children: [
              { index: true,          element: <Lazy><InventoryDashboard /></Lazy> },
              { path: 'receive',      element: <Lazy><ReceiveStockPage /></Lazy> },
              { path: 'issue',        element: <Lazy><IssueStockPage /></Lazy> },
              { path: 'transfer',     element: <Lazy><TransferPage /></Lazy> },
              { path: 'cycle',        element: <Lazy><CycleCountPage /></Lazy> },
              { path: 'search',       element: <Lazy><InventorySearchPage /></Lazy> },
            ],
          },

          // ── Crawling (ADMIN + PROCUREMENT_ANALYST) ─────────────────────────
          {
            path: 'crawling',
            element: <ProtectedRoute allowedRoles={['ADMIN', 'PROCUREMENT_ANALYST']} />,
            children: [
              { index: true,          element: <Lazy><CrawlingDashboard /></Lazy> },
              { path: 'sources',      element: <Lazy><NotImplementedPage /></Lazy> },
              { path: 'rules',        element: <Lazy><NotImplementedPage /></Lazy> },
              { path: 'tasks',        element: <Lazy><NotImplementedPage /></Lazy> },
              { path: 'debugger',     element: <Lazy><NotImplementedPage /></Lazy> },
            ],
          },

          // ── Admin (ADMIN only) ─────────────────────────────────────────────
          {
            path: 'admin',
            element: <ProtectedRoute allowedRoles={['ADMIN']} />,
            children: [
              { index: true,          element: <Lazy><AdminDashboard /></Lazy> },
              { path: 'users',        element: <Lazy><NotImplementedPage /></Lazy> },
              { path: 'audit',        element: <Lazy><NotImplementedPage /></Lazy> },
              { path: 'settings',     element: <Lazy><NotImplementedPage /></Lazy> },
            ],
          },

          // ── Catch-all ──────────────────────────────────────────────────────
          { path: '*', element: <Lazy><NotImplementedPage /></Lazy> },
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
