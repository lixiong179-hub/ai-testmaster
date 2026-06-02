/**
 * AI 调用审计 API 模块
 *
 * 对接后端 /api/v1/ai-invocation 端点，提供成本聚合与调用记录查询。
 * 成本单位统一为人民币元（与 ApiCostLog 一致），后端返回 cost_usd 字段
 * 在前端展示时按汇率转换为人民币元。
 */
import request from '@/utils/request'

// ============== 类型定义 ==============

/** 批次成本汇总信息 */
export interface BatchCostInfo {
  /** 总调用次数 */
  totalCalls: number
  /** 总输入 Token 数 */
  totalPromptTokens: number
  /** 总输出 Token 数 */
  totalCompletionTokens: number
  /** 总 Token 数（输入 + 输出） */
  totalTokens: number
  /** 估算成本（美元） */
  totalCostUsd: number
}

/** AI 调用成本聚合查询参数 */
export interface AIInvocationStatsParams {
  project_id: number
  start_date?: string
  end_date?: string
  group_by?: 'model' | 'strategy' | 'date'
}

/** AI 调用成本聚合结果项 */
export interface AIInvocationStatsItem {
  group_key: string
  total_calls: number
  total_prompt_tokens: number
  total_completion_tokens: number
  total_cost_usd: number
}

/** AI 调用成本聚合响应 */
export interface AIInvocationStatsResponse {
  items: AIInvocationStatsItem[]
}

/** AI 调用记录查询参数 */
export interface AIInvocationListParams {
  batch_id?: number
  project_id?: number
  page?: number
  page_size?: number
}

/** AI 调用记录列表项 */
export interface AIInvocationListItem {
  id: number
  run_id: number | null
  step_name: string | null
  model: string
  prompt_tokens: number
  completion_tokens: number
  cost_usd: number
  latency_ms: number
  status: string
  error_message: string | null
  created_at: string
  generation_batch_id: number | null
  scenario_type: string | null
  generation_strategy: string | null
  prompt_key: string | null
  prompt_version: number | null
  prompt_hash: string | null
  error_code: string | null
}

/** AI 调用记录分页响应 */
export interface AIInvocationListResponse {
  items: AIInvocationListItem[]
  total: number
  page: number
  page_size: number
}

// ============== 工具函数 ==============

/** USD 转 CNY 汇率常量（与 ApiCostLog 人民币元对齐） */
const USD_TO_CNY = 7.25

/** 将 USD 金额转换为人民币元 */
export function usdToCny(usd: number): number {
  return Number((usd * USD_TO_CNY).toFixed(4))
}

/** 从响应中提取 data 字段 */
function extractData<T>(response: unknown): T {
  const resp = response as { code?: number; data?: T }
  if (resp && resp.data !== undefined) return resp.data
  return response as T
}

// ============== API 封装 ==============

export const aiInvocationApi = {
  /**
   * 按批次 ID 查询成本汇总
   *
   * 通过 /list 接口获取该批次所有调用记录，
   * 在前端汇总 Token 数量和成本。
   *
   * @param batchId - 生成批次 ID
   * @returns 成本汇总信息
   */
  getBatchCost: async (batchId: number): Promise<BatchCostInfo> => {
    const response = await request.get('/api/v1/ai-invocation/list', {
      params: { batch_id: batchId, page: 1, page_size: 100 },
    })
    const data = extractData<AIInvocationListResponse>(response)
    const items = data.items || []

    let totalPromptTokens = 0
    let totalCompletionTokens = 0
    let totalCostUsd = 0

    for (const item of items) {
      totalPromptTokens += item.prompt_tokens || 0
      totalCompletionTokens += item.completion_tokens || 0
      totalCostUsd += item.cost_usd || 0
    }

    return {
      totalCalls: items.length,
      totalPromptTokens,
      totalCompletionTokens,
      totalTokens: totalPromptTokens + totalCompletionTokens,
      totalCostUsd,
    }
  },

  /** 获取 AI 调用成本聚合统计 */
  getStats: async (
    params: AIInvocationStatsParams
  ): Promise<{ code: number; message: string; data: AIInvocationStatsResponse }> => {
    return request.get('/api/v1/ai-invocation/stats', { params })
  },

  /** 获取 AI 调用记录分页列表 */
  getList: async (
    params: AIInvocationListParams
  ): Promise<{ code: number; message: string; data: AIInvocationListResponse }> => {
    return request.get('/api/v1/ai-invocation/list', { params })
  },
}

export default aiInvocationApi
