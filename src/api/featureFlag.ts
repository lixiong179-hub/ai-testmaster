import request from '@/utils/request'

/** FeatureFlag 条目 */
export interface FeatureFlagItem {
  key: string
  name: string
  description: string | null
  enabled: boolean
  rollout_percentage: number
  target_type: 'all' | 'specific'
  target_project_ids: number[]
  created_at: string
  updated_at: string | null
}

/** FeatureFlag 创建请求 */
export interface FeatureFlagCreate {
  key: string
  name: string
  description?: string
  enabled?: boolean
  rollout_percentage?: number
  target_type?: 'all' | 'specific'
  target_project_ids?: number[]
}

/** FeatureFlag 更新请求 */
export interface FeatureFlagUpdate {
  name?: string
  description?: string
  enabled?: boolean
  rollout_percentage?: number
  target_type?: 'all' | 'specific'
  target_project_ids?: number[]
}

/** FeatureFlag API封装 */
export const featureFlagApi = {
  /** 获取 FeatureFlag 列表 */
  getFeatureFlags: () => {
    return request.get<FeatureFlagItem[]>('/api/v1/feature-flag/')
  },

  /** 创建 FeatureFlag */
  createFeatureFlag: (data: FeatureFlagCreate) => {
    return request.post<FeatureFlagItem>('/api/v1/feature-flag/', data)
  },

  /** 更新 FeatureFlag */
  updateFeatureFlag: (key: string, data: FeatureFlagUpdate) => {
    return request.put<FeatureFlagItem>(`/api/v1/feature-flag/${key}`, data)
  },

  /** 删除 FeatureFlag */
  deleteFeatureFlag: (key: string) => {
    return request.delete(`/api/v1/feature-flag/${key}`)
  },

  /** 切换 FeatureFlag 启用状态 */
  toggleFeatureFlag: (key: string, enabled: boolean) => {
    return request.patch<FeatureFlagItem>(`/api/v1/feature-flag/${key}/toggle`, { enabled })
  },
}
