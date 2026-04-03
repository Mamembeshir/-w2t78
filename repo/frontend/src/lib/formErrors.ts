/**
 * formErrors.ts — Extract per-field validation errors from DRF API responses.
 *
 * DRF error shape (via config/exceptions.py):
 *   { code: string, message: string, details: { field: string | string[] } }
 *
 * Usage:
 *   const fieldErrors = extractFieldErrors(err)
 *   // { quantity: "Ensure this value is less than or equal to 9999999.9999.", ... }
 */

type ApiErrorResponse = {
  response?: {
    data?: {
      message?: string
      details?: Record<string, string | string[]>
    }
  }
}

/** Returns a flat map of field → first error string, or empty object if none. */
export function extractFieldErrors(err: unknown): Record<string, string> {
  const data = (err as ApiErrorResponse)?.response?.data
  if (!data?.details) return {}
  const out: Record<string, string> = {}
  for (const [field, val] of Object.entries(data.details)) {
    out[field] = Array.isArray(val) ? val[0] : String(val)
  }
  return out
}

/** Returns the top-level message string, with a fallback. */
export function extractMessage(err: unknown, fallback = 'An error occurred.'): string {
  return (err as ApiErrorResponse)?.response?.data?.message ?? fallback
}
