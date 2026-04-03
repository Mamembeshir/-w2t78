/**
 * src/lib/queryClient.ts
 * React Query client — tuned for a local-network, offline-first system.
 * No retries on 4xx (client errors are deterministic).
 * Stale time: 30s for most data (warehouse data changes slowly).
 */
import { QueryClient } from '@tanstack/react-query'
import { AxiosError } from 'axios'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,          // 30 seconds before background refetch
      gcTime: 5 * 60_000,         // 5 minutes in cache after unmount
      retry: (failureCount, error) => {
        // Don't retry client errors (4xx)
        if (error instanceof AxiosError && error.response) {
          const status = error.response.status
          if (status >= 400 && status < 500) return false
        }
        // Retry network errors up to 2 times (local network may blip)
        return failureCount < 2
      },
      refetchOnWindowFocus: false, // no refetch on tab switch (kiosk use)
    },
    mutations: {
      retry: false,
    },
  },
})
