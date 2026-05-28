import request from '@/utils/request'

/** 审计日志条目 */
export interface AuditLogItem {
  id: number
  action: string
  actor_id: number
  target_kind: string
  target_id: number
  detail: string
  run_id: number | null
  iteration_id: number | null
  created_at: string
}

/** 审计日志分页响应 */
export interface AuditLogListResponse {
  items: AuditLogItem[]
  total: number
  page: number
  page_size: number
}

/** 审计日志查询参数 */
export interface AuditLogQueryParams {
  target_kind?: string
  target_id?: number
  actor_id?: number
  action?: string
  since?: string
  until?: string
  page?: number
  page_size?: number
}

/** 审计日志API封装 */
export const auditLogApi = {
  /** 查询审计日志 */
  getLogs: (params: AuditLogQueryParams) => {
    return request.get<AuditLogListResponse>('/api/v1/audit-log/logs', { params })
  },
}

export default auditLogApi
