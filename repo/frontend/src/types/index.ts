// ── Role ─────────────────────────────────────────────────────────────────────
export type Role = 'ADMIN' | 'INVENTORY_MANAGER' | 'PROCUREMENT_ANALYST'

// ── User ─────────────────────────────────────────────────────────────────────
export interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  role: Role
  is_active: boolean
  last_login: string | null
  date_joined: string
}

// ── Auth ─────────────────────────────────────────────────────────────────────
export interface LoginResponse {
  access: string
  refresh: string
  user: User
}

export interface AuthContextType {
  user: User | null
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

// ── Navigation ───────────────────────────────────────────────────────────────
export interface NavItem {
  label: string
  path: string
  icon: React.ComponentType<{ className?: string }>
  roles: Role[]
}

// ── Toast ─────────────────────────────────────────────────────────────────────
export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface Toast {
  id: string
  type: ToastType
  message: string
  duration: number
}

export interface ToastContextType {
  toasts: Toast[]
  success: (message: string, duration?: number) => void
  error: (message: string, duration?: number) => void
  warning: (message: string, duration?: number) => void
  info: (message: string, duration?: number) => void
  dismiss: (id: string) => void
}

// ── Table ─────────────────────────────────────────────────────────────────────
export interface Column<T> {
  key: keyof T | string
  header: string
  sortable?: boolean
  className?: string
  render?: (value: unknown, row: T) => React.ReactNode
}

// ── Pagination ────────────────────────────────────────────────────────────────
export interface PageInfo {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}
