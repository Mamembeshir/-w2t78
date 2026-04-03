/**
 * useCrawling.ts — React Query hooks for Crawling API (Phase 6).
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface CrawlSource {
  id: number
  name: string
  base_url: string
  rate_limit_rpm: number
  crawl_delay_seconds: number
  user_agents: string[]
  is_active: boolean
  active_rule_version: number | null
  created_by: number | null
  created_at: string
}

export interface CrawlRuleVersion {
  id: number
  source: number
  version_number: number
  version_note: string
  is_active: boolean
  is_canary: boolean
  canary_pct: number
  canary_started_at: string | null
  canary_error_rate: number | null
  pagination_config: Record<string, unknown> | null
  parameters: Record<string, unknown> | null
  request_headers_masked: Record<string, string>
  created_by: number | null
  created_at: string
}

export interface CrawlTask {
  id: number
  source: number
  source_name: string
  rule_version: number | null
  fingerprint: string
  url: string
  status: 'PENDING' | 'WAITING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'RETRYING' | 'CANCELLED'
  priority: number
  attempt_count: number
  last_error: string
  checkpoint_page: number
  next_retry_at: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface CrawlRequestLog {
  id: number
  task: number
  request_url: string
  request_headers: string
  response_status: number | null
  response_snippet: string
  duration_ms: number
  timestamp: string
}

export interface SourceQuota {
  id: number
  source: number
  rpm_limit: number
  current_count: number
  window_start: string | null
  held_until: string | null
  utilization_pct: number
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// ── Sources ───────────────────────────────────────────────────────────────────

export function useSources() {
  return useQuery<PaginatedResponse<CrawlSource>>({
    queryKey: ['crawl-sources'],
    queryFn: () => api.get<PaginatedResponse<CrawlSource>>('/api/crawl/sources/?page_size=200').then(r => r.data),
  })
}

export function useSource(id: number | null) {
  return useQuery<CrawlSource>({
    queryKey: ['crawl-source', id],
    queryFn: () => api.get<CrawlSource>(`/api/crawl/sources/${id}/`).then(r => r.data),
    enabled: id != null,
  })
}

export function useCreateSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<CrawlSource>) =>
      api.post<CrawlSource>('/api/crawl/sources/', data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['crawl-sources'] }),
  })
}

export function useUpdateSource(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<CrawlSource>) =>
      api.patch<CrawlSource>(`/api/crawl/sources/${id}/`, data).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['crawl-sources'] })
      qc.invalidateQueries({ queryKey: ['crawl-source', id] })
    },
  })
}

// ── Rule Versions ─────────────────────────────────────────────────────────────

export function useRuleVersions(sourceId: number | null) {
  return useQuery<PaginatedResponse<CrawlRuleVersion>>({
    queryKey: ['crawl-rule-versions', sourceId],
    queryFn: () =>
      api.get<PaginatedResponse<CrawlRuleVersion>>(`/api/crawl/sources/${sourceId}/rule-versions/`).then(r => r.data),
    enabled: sourceId != null,
  })
}

export function useCreateRuleVersion(sourceId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { version_note: string; pagination_config?: unknown; parameters?: unknown }) =>
      api.post<CrawlRuleVersion>(`/api/crawl/sources/${sourceId}/rule-versions/`, data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['crawl-rule-versions', sourceId] }),
  })
}

export function useActivateVersion(sourceId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (versionId: number) =>
      api.post<CrawlRuleVersion>(`/api/crawl/rule-versions/${versionId}/activate/`).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['crawl-rule-versions', sourceId] })
      qc.invalidateQueries({ queryKey: ['crawl-source', sourceId] })
      qc.invalidateQueries({ queryKey: ['crawl-sources'] })
    },
  })
}

export function useStartCanary(sourceId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (versionId: number) =>
      api.post<CrawlRuleVersion>(`/api/crawl/rule-versions/${versionId}/canary/`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['crawl-rule-versions', sourceId] }),
  })
}

export function useRollbackCanary(sourceId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (versionId: number) =>
      api.post<CrawlRuleVersion>(`/api/crawl/rule-versions/${versionId}/rollback/`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['crawl-rule-versions', sourceId] }),
  })
}

// ── Tasks ─────────────────────────────────────────────────────────────────────

export function useTasks(statusFilter?: string, sourceId?: number) {
  return useQuery<PaginatedResponse<CrawlTask>>({
    queryKey: ['crawl-tasks', statusFilter, sourceId],
    queryFn: () => {
      const params = new URLSearchParams()
      if (statusFilter) params.set('status', statusFilter)
      if (sourceId) params.set('source_id', String(sourceId))
      return api.get<PaginatedResponse<CrawlTask>>(`/api/crawl/tasks/?${params}`).then(r => r.data)
    },
    refetchInterval: 5000,
  })
}

export function useEnqueueTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { source_id: number; url: string; parameters?: Record<string, unknown>; priority?: number }) =>
      api.post<{ deduplicated: boolean; task: CrawlTask }>('/api/crawl/tasks/', data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['crawl-tasks'] }),
  })
}

export function useRetryTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (taskId: number) =>
      api.post<CrawlTask>(`/api/crawl/tasks/${taskId}/retry/`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['crawl-tasks'] }),
  })
}

// ── Debug Log ─────────────────────────────────────────────────────────────────

export function useDebugLog(sourceId: number | null) {
  return useQuery<CrawlRequestLog[]>({
    queryKey: ['crawl-debug-log', sourceId],
    queryFn: () =>
      api.get<CrawlRequestLog[]>(`/api/crawl/sources/${sourceId}/debug-log/`).then(r => r.data),
    enabled: sourceId != null,
    refetchInterval: 10000,
  })
}

// ── Quota ─────────────────────────────────────────────────────────────────────

export function useSourceQuota(sourceId: number | null) {
  return useQuery<SourceQuota>({
    queryKey: ['crawl-quota', sourceId],
    queryFn: () =>
      api.get<SourceQuota>(`/api/crawl/sources/${sourceId}/quota/`).then(r => r.data),
    enabled: sourceId != null,
    refetchInterval: 5000,
  })
}
