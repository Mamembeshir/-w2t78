import { useEffect, useRef, type ReactNode } from 'react'
import { XMarkIcon } from './icons'

type ModalSize = 'sm' | 'md' | 'lg' | 'xl'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: ReactNode
  size?: ModalSize
  footer?: ReactNode
}

const sizeMap: Record<ModalSize, string> = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
}

export function Modal({ isOpen, onClose, title, children, size = 'md', footer }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null)

  // Focus trap + Escape key
  useEffect(() => {
    if (!isOpen) return

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') { onClose(); return }
      if (e.key !== 'Tab') return

      const focusable = panelRef.current?.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
      if (!focusable || focusable.length === 0) return

      const first = focusable[0]
      const last  = focusable[focusable.length - 1]

      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus() }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus() }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    panelRef.current?.focus()
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-modal flex items-end sm:items-center justify-center sm:p-4"
      aria-modal="true"
      role="dialog"
      aria-labelledby="modal-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel — bottom sheet on mobile, centered dialog on sm+ */}
      <div
        ref={panelRef}
        tabIndex={-1}
        className={`relative w-full ${sizeMap[size]}
          bg-surface-800 border border-surface-700/80
          rounded-t-2xl sm:rounded-2xl shadow-card-lg
          flex flex-col outline-none
          max-h-[90dvh] sm:max-h-[85vh]`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 sm:px-6 py-4 sm:py-5 border-b border-surface-700/80 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-0.5 h-5 rounded-full bg-primary-500/80 flex-shrink-0" />
            <h2 id="modal-title" className="text-base font-semibold text-text-primary tracking-tight">{title}</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-text-disabled hover:text-text-secondary hover:bg-surface-700/80 transition-colors"
            aria-label="Close"
          >
            <XMarkIcon className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-4 sm:px-6 py-5 sm:py-6 overflow-y-auto flex-1">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="px-4 sm:px-6 py-4 border-t border-surface-700/80 bg-surface-900/40 rounded-b-2xl flex items-center justify-end gap-3 flex-shrink-0 flex-wrap">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
