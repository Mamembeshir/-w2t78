import { createContext, useCallback, useState, type ReactNode } from 'react'
import type { Toast, ToastContextType, ToastType } from '@/types'

export const ToastContext = createContext<ToastContextType | null>(null)

function uid() {
  return Math.random().toString(36).slice(2, 9)
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const add = useCallback((type: ToastType, message: string, duration = 4000) => {
    const id = uid()
    setToasts((prev) => [...prev, { id, type, message, duration }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), duration)
  }, [])

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{
      toasts,
      success: (msg, dur) => add('success', msg, dur),
      error: (msg, dur) => add('error', msg, dur),
      warning: (msg, dur) => add('warning', msg, dur),
      info: (msg, dur) => add('info', msg, dur),
      dismiss,
    }}>
      {children}
    </ToastContext.Provider>
  )
}
