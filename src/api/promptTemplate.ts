import request from '@/utils/request'

/** Prompt 模板版本（对应后端 PromptTemplateResponse） */
export interface PromptTemplate {
  id: number
  prompt_key: string
  prompt_version: number
  prompt_hash: string
  content: string
  enabled: boolean
  is_default: boolean
  description: string | null
  created_at: string
}

/** 版本号类型别名 */
export type PromptVersion = number

/** 注册新版本请求体（对应后端 PromptTemplateCreate） */
export interface PromptTemplateCreate {
  prompt_key: string
  content: string
  description?: string
}

/** 列表查询参数 */
export interface PromptTemplateListParams {
  prompt_key?: string
  page?: number
  page_size?: number
}

/** 列表响应（对应后端 PromptTemplateListResponse） */
export interface PromptTemplateListResponse {
  items: PromptTemplate[]
  total: number
  page: number
  page_size: number
}

/** 设为默认版本请求体（对应后端 SetDefaultRequest） */
export interface SetDefaultRequest {
  version: number
}

/** 回滚请求体（对应后端 RollbackRequest） */
export interface RollbackRequest {
  target_version: number
}

/** 按 key 分组的 Prompt 注册表项，便于左侧树/列表展示 */
export interface PromptRegistry {
  key: string
  versions: PromptTemplate[]
  defaultVersion: PromptTemplate | null
  latestVersion: PromptTemplate | null
}

/**
 * Prompt 模板 API 封装。
 *
 * 后端路由前缀：/api/v1/prompt-templates（见 app/main.py）。
 * 端点：list / register / set-default / rollback。
 * 「运行时内容」即某 key 的默认版本内容，由 getRuntimeContent 基于 list 端点聚合得到。
 */
export const promptTemplateApi = {
  /** 获取 Prompt 模板列表，支持按 prompt_key 筛选与分页 */
  getList: (params?: PromptTemplateListParams) => {
    return request.get<PromptTemplateListResponse>('/api/v1/prompt-templates/', {
      params,
    })
  },

  /** 获取指定 key 的全部版本（一次性拉满，前端分组展示用） */
  getVersionsByKey: async (key: string): Promise<PromptTemplate[]> => {
    const response = await request.get<PromptTemplateListResponse>(
      '/api/v1/prompt-templates/',
      { params: { prompt_key: key, page: 1, page_size: 100 } }
    )
    return response.data?.items ?? []
  },

  /** 获取指定 key 的运行时内容（默认版本内容；无默认时取最高版本兜底） */
  getRuntimeContent: async (key: string): Promise<string | null> => {
    const versions = await promptTemplateApi.getVersionsByKey(key)
    const defaultVersion = versions.find((v) => v.is_default) ?? null
    const fallback = versions[versions.length - 1] ?? null
    return (defaultVersion ?? fallback)?.content ?? null
  },

  /** 注册 Prompt 新版本 */
  registerVersion: (data: PromptTemplateCreate) => {
    return request.post<PromptTemplate>('/api/v1/prompt-templates/', data)
  },

  /** 将指定版本设为默认版本 */
  setDefault: (key: string, version: number) => {
    const payload: SetDefaultRequest = { version }
    return request.post<PromptTemplate>(
      `/api/v1/prompt-templates/${encodeURIComponent(key)}/set-default`,
      payload
    )
  },

  /** 回滚到指定版本（设为默认并禁用更高版本） */
  rollback: (key: string, targetVersion: number) => {
    const payload: RollbackRequest = { target_version: targetVersion }
    return request.post<PromptTemplate>(
      `/api/v1/prompt-templates/${encodeURIComponent(key)}/rollback`,
      payload
    )
  },
}

export default promptTemplateApi
