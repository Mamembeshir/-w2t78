/**
 * BarcodeScanner.tsx
 *
 * Camera-based barcode/QR code scanner using @ericblade/quagga2
 * (bundled locally — no CDN dependency).
 *
 * Supports all standard 1D barcodes (Code128, EAN, UPC, Code39) and QR codes.
 * Renders a live camera preview inside a modal overlay.
 * On successful detection, calls onDetected(code) once, then auto-closes.
 *
 * Usage:
 *   <BarcodeScanner isOpen={scanning} onDetected={setScanValue} onClose={() => setScanning(false)} />
 */
import { useEffect, useRef, useState } from 'react'
import Quagga from '@ericblade/quagga2'
import { XMarkIcon } from './icons'

interface BarcodeScannerProps {
  isOpen: boolean
  onDetected: (code: string) => void
  onClose: () => void
}

export function BarcodeScanner({ isOpen, onDetected, onClose }: BarcodeScannerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [initializing, setInitializing] = useState(true)

  useEffect(() => {
    if (!isOpen) return

    setError(null)
    setInitializing(true)

    // Short delay to allow the DOM to render before Quagga attaches the video stream
    const initTimer = setTimeout(() => {
      if (!containerRef.current) return

      Quagga.init(
        {
          inputStream: {
            name: 'Live',
            type: 'LiveStream',
            target: containerRef.current,
            constraints: {
              width: { min: 480 },
              height: { min: 320 },
              facingMode: 'environment', // rear camera on mobile devices
            },
          },
          locator: { patchSize: 'medium', halfSample: true },
          numOfWorkers: navigator.hardwareConcurrency
            ? Math.min(navigator.hardwareConcurrency, 4)
            : 2,
          frequency: 10,
          decoder: {
            readers: [
              'code_128_reader',
              'ean_reader',
              'ean_8_reader',
              'upc_reader',
              'upc_e_reader',
              'code_39_reader',
              'code_39_vin_reader',
              'codabar_reader',
              'i2of5_reader',
            ],
          },
          locate: true,
        },
        (err) => {
          setInitializing(false)
          if (err) {
            setError(
              err instanceof Error && err.message.includes('permission')
                ? 'Camera access denied. Please allow camera permissions and try again.'
                : 'Camera not available. Use keyboard entry instead.',
            )
            return
          }
          Quagga.start()
        },
      )

      // Listen for successful decode — deduplicate rapid-fire detections
      let lastCode = ''
      let lastTime = 0
      Quagga.onDetected((result) => {
        const code = result?.codeResult?.code
        if (!code) return
        const now = Date.now()
        if (code === lastCode && now - lastTime < 2000) return
        lastCode = code
        lastTime = now
        onDetected(code)
        handleClose()
      })
    }, 150)

    return () => {
      clearTimeout(initTimer)
      Quagga.offDetected()
      Quagga.stop()
    }
  }, [isOpen]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleClose() {
    Quagga.offDetected()
    Quagga.stop()
    onClose()
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-modal flex flex-col items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
      aria-modal="true"
      role="dialog"
      aria-label="Barcode scanner"
    >
      {/* Close button */}
      <button
        onClick={handleClose}
        className="absolute top-4 right-4 p-2 rounded-xl bg-surface-800 border border-surface-700 text-text-secondary hover:text-text-primary transition-colors"
        aria-label="Close scanner"
      >
        <XMarkIcon className="w-6 h-6" />
      </button>

      <div className="w-full max-w-md">
        <h2 className="text-center text-text-primary font-semibold mb-3 text-lg">
          Point camera at barcode
        </h2>

        {error ? (
          <div className="bg-surface-800 border border-danger-500 rounded-2xl p-6 text-center">
            <p className="text-danger-400 mb-4">{error}</p>
            <button
              onClick={handleClose}
              className="px-4 py-2 rounded-xl bg-surface-700 text-text-primary text-sm hover:bg-surface-600 transition-colors"
            >
              Use keyboard entry
            </button>
          </div>
        ) : (
          <div className="relative rounded-2xl overflow-hidden border-2 border-primary-500 bg-black">
            {/* Quagga attaches its video element here */}
            <div ref={containerRef} className="w-full" style={{ minHeight: 280 }} />

            {/* Scanner guide overlay */}
            <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
              <div className="w-3/4 h-1/2 border-2 border-primary-400 rounded-lg opacity-60" />
            </div>

            {initializing && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/60">
                <div className="text-center text-white">
                  <div className="w-8 h-8 border-2 border-white border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  <p className="text-sm">Starting camera…</p>
                </div>
              </div>
            )}
          </div>
        )}

        <p className="text-center text-text-muted text-sm mt-3">
          Supported: Code128, EAN, UPC, Code39 and more
        </p>
      </div>
    </div>
  )
}
