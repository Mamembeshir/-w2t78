import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { Cog6ToothIcon } from '@/components/ui/icons'

export function NotImplementedPage() {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-5 p-6">
      <div className="w-16 h-16 rounded-2xl bg-surface-700 flex items-center justify-center">
        <Cog6ToothIcon className="w-8 h-8 text-text-muted" />
      </div>
      <div className="text-center">
        <h2 className="text-lg font-semibold text-text-primary">Coming soon</h2>
        <p className="text-sm text-text-muted mt-1 max-w-xs">
          This feature is planned for a future phase of development.
        </p>
      </div>
      <Button variant="secondary" onClick={() => navigate(-1)}>Go back</Button>
    </div>
  )
}
