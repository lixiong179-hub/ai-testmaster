import request from '@/utils/request'

/** 质量规则条目 */
export interface QualityRuleItem {
  rule_key: string
  rule_value: string | number | boolean
  default_value: string | number | boolean
  description: string | null
  value_type: 'string' | 'number' | 'boolean' | 'enum'
  enum_options?: string[]
}

/** 质量规则更新请求 */
export interface QualityRuleUpdateRequest {
  rule_key: string
  rule_value: string | number | boolean
}

/** 质量规则API封装
 *
 * 路径以后端实际挂载为准（B-08 修复 2026-11-12）：
 * `app/main.py` 以 prefix `/api/v1/projects` 挂载 `quality_rule.router`，
 * 端点为 `/{project_id}/quality-rules` → `/api/v1/projects/{project_id}/quality-rules`。
 * 原实现写作 `/api/v1/quality-rule/project/{id}`（无对应路由，线上会 404）。
 */
export const qualityRuleApi = {
  /** 获取项目级质量规则列表 */
  getQualityRules: (projectId: number) => {
    return request.get<QualityRuleItem[]>(`/api/v1/projects/${projectId}/quality-rules`)
  },

  /** 更新项目级质量规则 */
  updateQualityRule: (projectId: number, data: QualityRuleUpdateRequest) => {
    return request.put<QualityRuleItem>(`/api/v1/projects/${projectId}/quality-rules`, data)
  },
}
