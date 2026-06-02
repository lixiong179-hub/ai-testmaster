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

/** 质量规则API封装 */
export const qualityRuleApi = {
  /** 获取项目级质量规则列表 */
  getQualityRules: (projectId: number) => {
    return request.get<QualityRuleItem[]>(`/api/v1/quality-rule/project/${projectId}`)
  },

  /** 更新项目级质量规则 */
  updateQualityRule: (projectId: number, data: QualityRuleUpdateRequest) => {
    return request.put<QualityRuleItem>(`/api/v1/quality-rule/project/${projectId}`, data)
  },
}
