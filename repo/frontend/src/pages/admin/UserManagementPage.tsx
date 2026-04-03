import { useState } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { DataTable } from '@/components/ui/DataTable'
import { Badge, RoleBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/Toast'
import { useUsers, useCreateUser, useUpdateUser } from '@/hooks/useAdmin'
import type { UserRecord } from '@/hooks/useAdmin'
import type { Column } from '@/types'
import { api } from '@/lib/api'

// ── Constants ─────────────────────────────────────────────────────────────────

const ROLE_OPTIONS = [
  { value: 'ADMIN',              label: 'Admin' },
  { value: 'INVENTORY_MANAGER',  label: 'Inventory Manager' },
  { value: 'PROCUREMENT_ANALYST', label: 'Procurement Analyst' },
  { value: 'VIEWER',             label: 'Viewer' },
]

// ── Types ─────────────────────────────────────────────────────────────────────

interface UserRow extends Record<string, unknown> {
  id: string
  username: string
  full_name: string
  email: string
  role: string
  is_active: boolean
  last_login: string | null
  date_joined: string
}

// ── Main Component ────────────────────────────────────────────────────────────

export function UserManagementPage() {
  const toast = useToast()
  const { data, isLoading } = useUsers()
  const createUser = useCreateUser()
  const updateUser = useUpdateUser()

  const [showCreate, setShowCreate] = useState(false)
  const [editTarget, setEditTarget] = useState<UserRecord | null>(null)
  const [resetTarget, setResetTarget] = useState<UserRecord | null>(null)

  // Create form state
  const [createForm, setCreateForm] = useState({
    username: '', password: '', email: '', first_name: '', last_name: '',
    role: 'VIEWER', is_active: true,
  })
  const [createErrors, setCreateErrors] = useState<Record<string, string>>({})

  // Edit form state
  const [editRole, setEditRole] = useState('')
  const [editActive, setEditActive] = useState(true)

  // Reset password state
  const [newPassword, setNewPassword] = useState('')
  const [resetError, setResetError] = useState('')

  // ── Rows ──────────────────────────────────────────────────────────────────
  const rows: UserRow[] = (data?.results ?? []).map(u => ({
    id: String(u.id),
    username: u.username,
    full_name: [u.first_name, u.last_name].filter(Boolean).join(' ') || '—',
    email: u.email || '—',
    role: u.role,
    is_active: u.is_active,
    last_login: u.last_login,
    date_joined: u.date_joined,
  }))

  // ── Columns ───────────────────────────────────────────────────────────────
  const COLUMNS: Column<UserRow>[] = [
    {
      key: 'username',
      header: 'Username',
      sortable: true,
      className: 'font-medium text-text-primary',
    },
    {
      key: 'full_name',
      header: 'Full Name',
      sortable: false,
    },
    {
      key: 'email',
      header: 'Email',
      sortable: false,
      className: 'font-mono text-xs',
    },
    {
      key: 'role',
      header: 'Role',
      sortable: true,
      render: (v) => <RoleBadge role={String(v)} />,
    },
    {
      key: 'is_active',
      header: 'Active',
      sortable: true,
      render: (v) => (
        <Badge variant={v ? 'success' : 'danger'}>{v ? 'Active' : 'Inactive'}</Badge>
      ),
    },
    {
      key: 'last_login',
      header: 'Last Login',
      sortable: false,
      render: (v) => v ? new Date(v as string).toLocaleString() : '—',
    },
    {
      key: 'date_joined',
      header: 'Joined',
      sortable: true,
      render: (v) => new Date(v as string).toLocaleDateString(),
    },
    {
      key: 'id',
      header: 'Actions',
      sortable: false,
      render: (_, row) => {
        const user = data?.results.find(u => String(u.id) === row.id)
        if (!user) return null
        return (
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setEditTarget(user)
                setEditRole(user.role)
                setEditActive(user.is_active)
              }}
            >
              Edit
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setResetTarget(user)
                setNewPassword('')
                setResetError('')
              }}
            >
              Reset PW
            </Button>
          </div>
        )
      },
    },
  ]

  // ── Handlers ──────────────────────────────────────────────────────────────

  function handleCreateField(field: keyof typeof createForm, value: string | boolean) {
    setCreateForm(prev => ({ ...prev, [field]: value }))
    setCreateErrors(prev => { const n = { ...prev }; delete n[field]; return n })
  }

  async function handleCreate() {
    const errs: Record<string, string> = {}
    if (!createForm.username) errs.username = 'Required'
    if (!createForm.password || createForm.password.length < 10)
      errs.password = 'Minimum 10 characters'
    if (Object.keys(errs).length) { setCreateErrors(errs); return }

    try {
      await createUser.mutateAsync(createForm)
      toast.success('User created successfully')
      setShowCreate(false)
      setCreateForm({ username: '', password: '', email: '', first_name: '', last_name: '', role: 'VIEWER', is_active: true })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: Record<string, string[]> } })?.response?.data
      if (detail && typeof detail === 'object') {
        const fieldErrors: Record<string, string> = {}
        for (const [k, v] of Object.entries(detail)) {
          fieldErrors[k] = Array.isArray(v) ? v[0] : String(v)
        }
        setCreateErrors(fieldErrors)
      } else {
        toast.error('Failed to create user')
      }
    }
  }

  async function handleEdit() {
    if (!editTarget) return
    try {
      await updateUser.mutateAsync({ id: editTarget.id, role: editRole, is_active: editActive })
      toast.success('User updated')
      setEditTarget(null)
    } catch {
      toast.error('Failed to update user')
    }
  }

  async function handleResetPassword() {
    if (!resetTarget) return
    setResetError('')
    if (!newPassword || newPassword.length < 10) {
      setResetError('Minimum 10 characters')
      return
    }
    try {
      await api.post(`/api/users/${resetTarget.id}/reset-password/`, { new_password: newPassword })
      toast.success(`Password reset for ${resetTarget.username}`)
      setResetTarget(null)
      setNewPassword('')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setResetError(msg ?? 'Failed to reset password')
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <PageWrapper
      title="User Management"
      subtitle={`${data?.count ?? 0} user${data?.count !== 1 ? 's' : ''} total`}
      actions={
        <Button onClick={() => { setShowCreate(true); setCreateErrors({}) }}>
          + New User
        </Button>
      }
    >
      <DataTable<UserRow>
        columns={COLUMNS}
        rows={rows}
        rowKey="id"
        isLoading={isLoading}
        emptyMessage="No users found."
      />

      {/* ── Create Modal ── */}
      <Modal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        title="Create User"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button onClick={handleCreate} loading={createUser.isPending}>Create</Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Input
            label="Username"
            required
            value={createForm.username}
            onChange={v => handleCreateField('username', v)}
            error={createErrors.username}
          />
          <Input
            label="Password"
            type="password"
            required
            value={createForm.password}
            onChange={v => handleCreateField('password', v)}
            error={createErrors.password}
            helpText="Minimum 10 characters"
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="First Name"
              value={createForm.first_name}
              onChange={v => handleCreateField('first_name', v)}
            />
            <Input
              label="Last Name"
              value={createForm.last_name}
              onChange={v => handleCreateField('last_name', v)}
            />
          </div>
          <Input
            label="Email"
            type="email"
            value={createForm.email}
            onChange={v => handleCreateField('email', v)}
            error={createErrors.email}
          />
          <Select
            label="Role"
            required
            options={ROLE_OPTIONS}
            value={createForm.role}
            onChange={v => handleCreateField('role', v)}
          />
          <label className="flex items-center gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={createForm.is_active}
              onChange={e => handleCreateField('is_active', e.target.checked)}
              className="w-4 h-4 rounded border-surface-600 text-primary-500"
            />
            <span className="text-sm text-text-secondary">Active account</span>
          </label>
          {createErrors.non_field_errors && (
            <p className="text-danger-400 text-sm">{createErrors.non_field_errors}</p>
          )}
        </div>
      </Modal>

      {/* ── Edit Modal ── */}
      <Modal
        isOpen={editTarget !== null}
        onClose={() => setEditTarget(null)}
        title={`Edit User: ${editTarget?.username ?? ''}`}
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditTarget(null)}>Cancel</Button>
            <Button onClick={handleEdit} loading={updateUser.isPending}>Save</Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Select
            label="Role"
            required
            options={ROLE_OPTIONS}
            value={editRole}
            onChange={setEditRole}
          />
          <label className="flex items-center gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={editActive}
              onChange={e => setEditActive(e.target.checked)}
              className="w-4 h-4 rounded border-surface-600 text-primary-500"
            />
            <span className="text-sm text-text-secondary">Active account</span>
          </label>
        </div>
      </Modal>

      {/* ── Reset Password Modal ── */}
      <Modal
        isOpen={resetTarget !== null}
        onClose={() => setResetTarget(null)}
        title={`Reset Password: ${resetTarget?.username ?? ''}`}
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setResetTarget(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleResetPassword}>Reset Password</Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Input
            label="New Password"
            type="password"
            required
            value={newPassword}
            onChange={setNewPassword}
            error={resetError}
            helpText="Minimum 10 characters"
          />
        </div>
      </Modal>
    </PageWrapper>
  )
}
