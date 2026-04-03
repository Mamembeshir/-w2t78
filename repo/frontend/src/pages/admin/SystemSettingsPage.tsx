import { useState } from 'react'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/hooks/useToast'
import { api } from '@/lib/api'

interface SettingsForm {
  smtp_host: string
  smtp_port: string
  smtp_use_tls: boolean
  sms_gateway_url: string
}

interface SettingsResponse {
  smtp_host: string
  smtp_port: number
  smtp_use_tls: boolean
  sms_gateway_url: string
}

export function SystemSettingsPage() {
  const toast = useToast()
  const [form, setForm] = useState<SettingsForm>({
    smtp_host: '',
    smtp_port: '25',
    smtp_use_tls: false,
    sms_gateway_url: '',
  })
  const [loaded, setLoaded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState<'smtp' | 'sms' | null>(null)

  // Load current settings on first render
  if (!loaded) {
    setLoaded(true)
    api.get<SettingsResponse>('/api/settings/')
      .then(r => {
        setForm({
          smtp_host: r.data.smtp_host ?? '',
          smtp_port: String(r.data.smtp_port ?? 25),
          smtp_use_tls: r.data.smtp_use_tls ?? false,
          sms_gateway_url: r.data.sms_gateway_url ?? '',
        })
      })
      .catch(() => {
        // Settings endpoint may not exist in all deployments — that's fine,
        // the form stays at empty defaults.
      })
  }

  function set(field: keyof SettingsForm, value: string | boolean) {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await api.patch('/api/settings/', {
        smtp_host: form.smtp_host,
        smtp_port: parseInt(form.smtp_port, 10) || 25,
        smtp_use_tls: form.smtp_use_tls,
        sms_gateway_url: form.sms_gateway_url,
      })
      toast.success('Settings saved')
    } catch {
      toast.error('Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  async function handleTestSmtp() {
    setTesting('smtp')
    try {
      await api.post('/api/settings/test-smtp/')
      toast.success('SMTP test succeeded — check your inbox')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      toast.error(msg ?? 'SMTP test failed')
    } finally {
      setTesting(null)
    }
  }

  async function handleTestSms() {
    setTesting('sms')
    try {
      await api.post('/api/settings/test-sms/')
      toast.success('SMS gateway test succeeded')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      toast.error(msg ?? 'SMS gateway test failed')
    } finally {
      setTesting(null)
    }
  }

  return (
    <PageWrapper title="System Settings" subtitle="Configure notification gateways">
      <div className="max-w-2xl space-y-8">

        {/* SMTP */}
        <section className="bg-surface-800 border border-surface-700 rounded-2xl p-6">
          <h2 className="text-base font-semibold text-text-primary mb-1">SMTP Gateway</h2>
          <p className="text-sm text-text-muted mb-5">
            Outbound email for notifications. Leave blank to queue messages only (no delivery).
          </p>
          <div className="space-y-4">
            <Input
              label="SMTP Host"
              placeholder="mail.local"
              value={form.smtp_host}
              onChange={v => set('smtp_host', v)}
              helpText="Hostname of your locally hosted SMTP server"
            />
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Port"
                type="number"
                value={form.smtp_port}
                onChange={v => set('smtp_port', v)}
              />
              <label className="flex items-end gap-3 pb-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={form.smtp_use_tls}
                  onChange={e => set('smtp_use_tls', e.target.checked)}
                  className="w-4 h-4 rounded border-surface-600 text-primary-500"
                />
                <span className="text-sm text-text-secondary">Use STARTTLS</span>
              </label>
            </div>
            <div className="flex justify-end">
              <Button
                variant="secondary"
                size="sm"
                loading={testing === 'smtp'}
                onClick={handleTestSmtp}
                disabled={!form.smtp_host}
              >
                Test SMTP Connection
              </Button>
            </div>
          </div>
        </section>

        {/* SMS */}
        <section className="bg-surface-800 border border-surface-700 rounded-2xl p-6">
          <h2 className="text-base font-semibold text-text-primary mb-1">SMS Gateway</h2>
          <p className="text-sm text-text-muted mb-5">
            Outbound SMS for notifications. Must be a locally hosted gateway (no external providers).
          </p>
          <div className="space-y-4">
            <Input
              label="Gateway URL"
              placeholder="http://sms-gateway.local/send"
              value={form.sms_gateway_url}
              onChange={v => set('sms_gateway_url', v)}
              helpText="POST endpoint that accepts { to, message } JSON"
            />
            <div className="flex justify-end">
              <Button
                variant="secondary"
                size="sm"
                loading={testing === 'sms'}
                onClick={handleTestSms}
                disabled={!form.sms_gateway_url}
              >
                Test SMS Gateway
              </Button>
            </div>
          </div>
        </section>

        {/* Save */}
        <div className="flex justify-end">
          <Button onClick={handleSave} loading={saving}>
            Save Settings
          </Button>
        </div>
      </div>
    </PageWrapper>
  )
}
