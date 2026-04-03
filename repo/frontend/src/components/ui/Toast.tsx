import { useToast } from '@/hooks/useToast'
import type { Toast as ToastItem } from '@/types'
import { CheckIcon, ExclamationTriangleIcon, InformationCircleIcon, XMarkIcon } from './icons'

const configs = {
  success: { icon: CheckIcon,              border: 'border-success-500/40', text: 'text-success-400', bg: 'bg-success-500/10' },
  error:   { icon: ExclamationTriangleIcon, border: 'border-danger-500/40',  text: 'text-danger-400',  bg: 'bg-danger-500/10'  },
  warning: { icon: ExclamationTriangleIcon, border: 'border-warning-500/40', text: 'text-warning-400', bg: 'bg-warning-500/10' },
  info:    { icon: InformationCircleIcon,   border: 'border-info-500/40',    text: 'text-info-400',    bg: 'bg-info-500/10'    },
}

function ToastItem({ toast }: { toast: ToastItem }) {
  const { dismiss } = useToast()
  const { icon: Icon, border, text, bg } = configs[toast.type]

  return (
    <div className={`flex items-start gap-3 w-80 ${bg} border ${border} rounded-xl px-4 py-3 shadow-card-md pointer-events-auto`}>
      <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${text}`} />
      <p className="flex-1 text-sm text-text-primary leading-snug">{toast.message}</p>
      <button
        onClick={() => dismiss(toast.id)}
        className="flex-shrink-0 text-text-muted hover:text-text-primary transition-colors"
        aria-label="Dismiss"
      >
        <XMarkIcon className="w-4 h-4" />
      </button>
    </div>
  )
}

/** Rendered inside AppShell — fixed top-right, stacks upward */
export function ToastContainer() {
  const { toasts } = useToast()
  return (
    <div
      className="fixed top-4 right-4 z-toast flex flex-col gap-2 pointer-events-none"
      aria-live="polite"
      aria-atomic="false"
    >
      {toasts.map((t) => <ToastItem key={t.id} toast={t} />)}
    </div>
  )
}
