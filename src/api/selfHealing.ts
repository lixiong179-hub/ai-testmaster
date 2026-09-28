import request from '@/utils/request'
import type { ApiResponse } from '@/utils/request'

/**
 * 自愈管理 API 封装。
 *
 * 对应后端 app/api/v1/endpoints/self_healing.py，路由前缀 /api/v1。
 * 提供：审计分页列表、审计详情、回滚、项目级自愈配置查询/更新、Prometheus 指标。
 */

// ============== 类型定义 ==============

/** 自愈审计记录（对应后端 AuditResponse / SelfHealingAudit 表） */
export interface SelfHealingAudit {
  id: number
  test_case_id: number
  step_index: number
  locator_id: number | null
  old_selector: string | null
  new_selector: string | null
  failure_type: string
  strategy: string
  confidence: number | null
  token_cost: number
  low_confidence: boolean
  created_at: string
}

/** 审计分页列表数据 */
export interface AuditListData {
  items: SelfHealingAudit[]
  total: number
  page: number
  page_size: number
}

/** 回滚响应数据 */
export interface RollbackData {
  audit_id: number
  restored_selector: string
  new_audit_id: number
  message: string
}

/** 项目级自愈配置（enabled 已合并全局开关） */
export interface SelfHealingConfig {
  enabled: boolean
  strategies: string[]
  token_limit: number
}

/** 自愈配置更新请求（字段全可选，仅更新传入字段） */
export interface SelfHealingConfigUpdate {
  enabled?: boolean
  strategies?: string[]
  token_limit?: number
}

/** 审计列表查询参数（后端仅支持 project_id/test_case_id/page/page_size） */
export interface AuditListParams {
  project_id?: number
  test_case_id?: number
  page?: number
  page_size?: number
}

// ============== 选项常量（与后端合法值对齐） ==============

/**
 * 失败类型选项（对应后端 SELF_HEAL_FAILURE_TYPE label：element_gone/dom_changed/load_delay/env_noise）。
 */
export const failureTypeOptions = [
  { label: '元素消失', value: 'element_gone' },
  { label: 'DOM变更', value: 'dom_changed' },
  { label: '加载延迟', value: 'load_delay' },
  { label: '环境噪声', value: 'env_noise' },
] as const

/**
 * 自愈策略选项（对应后端 SelfHealingConfigUpdate.strategies 合法值 mcp/vision/stagehand）。
 */
export const strategyOptions = [
  { label: 'MCP', value: 'mcp' },
  { label: '视觉识别', value: 'vision' },
  { label: 'Stagehand', value: 'stagehand' },
] as const

// ============== API 封装 ==============

export const selfHealingApi = {
  /** 分页查询自愈审计记录，支持按项目/用例过滤 */
  getAudits: async (params: AuditListParams): Promise<ApiResponse<AuditListData>> => {
    return request.get('/api/v1/self-healing/audits', { params })
  },

  /** 获取单条自愈审计详情，不存在返回 404 */
  getAudit: async (auditId: number): Promise<ApiResponse<SelfHealingAudit>> => {
    return request.get(`/api/v1/self-healing/audits/${auditId}`)
  },

  /** 回滚指定审计记录的自愈变更，恢复旧选择器并写入回滚审计 */
  rollbackAudit: async (auditId: number): Promise<ApiResponse<RollbackData>> => {
    return request.post(`/api/v1/self-healing/audits/${auditId}/rollback`)
  },

  /** 查询项目级自愈配置 */
  getConfig: async (projectId: number): Promise<ApiResponse<SelfHealingConfig>> => {
    return request.get(`/api/v1/projects/${projectId}/self-healing-config`)
  },

  /** 更新项目级自愈配置，仅更新传入字段 */
  updateConfig: async (
    projectId: number,
    data: SelfHealingConfigUpdate
  ): Promise<ApiResponse<SelfHealingConfig>> => {
    return request.put(`/api/v1/projects/${projectId}/self-healing-config`, data)
  },

  /**
   * 获取 Prometheus 自愈指标（文本格式，由全局 /metrics 端点暴露）。
   * 返回值为标准 Prometheus exposition 格式字符串，非业务 JSON。
   */
  getMetrics: async (): Promise<ApiResponse<string>> => {
    return request.get('/metrics', { responseType: 'text' })
  },
}

export default selfHealingApi
