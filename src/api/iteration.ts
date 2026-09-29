import request from '@/utils/request'

export interface Iteration {
  id: number
  project_id: number
  name: string
  version: string
  description?: string
  status: string
  start_date?: string
  end_date?: string
  create_time: string
  update_time: string
}

export interface IterationListResponse {
  code: number
  message: string
  data: {
    items: Iteration[]
    total: number
    page: number
    page_size: number
  }
}

export interface IterationCreateRequest {
  project_id: number
  name: string
  version?: string
  description?: string
  start_date?: string
  end_date?: string
}

export interface IterationUpdateRequest {
  name?: string
  version?: string
  description?: string
  start_date?: string
  end_date?: string
}

export interface IterationResponse {
  code: number
  message: string
  data: Iteration
}

export interface IterationInputRequest {
  kind: string
  file_id?: number | null
  payload?: Record<string, unknown>
  hash?: string
}

/** 生命周期终态主操作（定稿 / 启动 Pipeline / 归档）的响应载荷 */

/** Pipeline 启动响应（后端 POST /iteration/{id}/pipeline/run） */
export interface PipelineRunResponse {
  run_id: number
  iteration_id: number
  status: string
  /** 场景编号：1=冒烟 2=… 3=回归 4=UI 回归 */
  scenario: number
}

/** 统一返回结构（成功走后端 create_response，失败由本层兜底为 code=-1） */
export interface IterationApiResult<T> {
  code: number
  msg: string
  message: string
  data: T | null
}

/**
 * 把异常转换为标准错误返回（与后端 create_response 的错误分支字段保持一致）
 * @param error 捕获到的异常
 * @param fallbackMessage 非 Error 异常时的兜底文案
 */
function toErrorResult<T>(error: unknown, fallbackMessage: string): IterationApiResult<T> {
  const message = error instanceof Error && error.message ? error.message : fallbackMessage
  return { code: -1, msg: message, message, data: null }
}

/**
 * 迭代定稿（in_review → finalized）
 * POST /api/v1/iteration/{iterationId}/finalize
 */
export async function finalizeIteration(
  iterationId: number
): Promise<IterationApiResult<Iteration>> {
  try {
    const res = await request.post(`/api/v1/iteration/${iterationId}/finalize`)
    return res as unknown as IterationApiResult<Iteration>
  } catch (error) {
    return toErrorResult<Iteration>(error, '定稿迭代失败')
  }
}

/**
 * 启动迭代 Pipeline
 * POST /api/v1/iteration/{iterationId}/pipeline/run
 * @param iterationId 迭代 ID
 * @param scenario 场景编号（默认 1=冒烟）
 */
export async function runPipeline(
  iterationId: number,
  scenario: number = 1
): Promise<IterationApiResult<PipelineRunResponse>> {
  try {
    const res = await request.post(`/api/v1/iteration/${iterationId}/pipeline/run`, { scenario })
    return res as unknown as IterationApiResult<PipelineRunResponse>
  } catch (error) {
    return toErrorResult<PipelineRunResponse>(error, '启动 Pipeline 失败')
  }
}

/**
 * 归档迭代（finalized → archived）
 * POST /api/v1/iteration/{iterationId}/archive
 *
 * ⚠️ 后端当前**未注册**该路由（`app/api/v1/endpoints/iteration/_routes.py` 仅有
 * finalize 与 pipeline/run）；本函数按既有约定先行提供，待后端补齐后即可直接使用，
 * 调用失败时返回 `code=-1` 而不会抛出。
 */
export async function archiveIteration(
  iterationId: number
): Promise<IterationApiResult<Iteration>> {
  try {
    const res = await request.post(`/api/v1/iteration/${iterationId}/archive`)
    return res as unknown as IterationApiResult<Iteration>
  } catch (error) {
    return toErrorResult<Iteration>(error, '归档迭代失败')
  }
}

export const iterationApi = {
  getIterations: async (
    projectId: number,
    page: number = 1,
    pageSize: number = 100
  ): Promise<IterationListResponse> => {
    return request.get(`/api/v1/iteration/list/${projectId}`, {
      params: { page, page_size: pageSize },
    })
  },

  getIteration: async (iterationId: number): Promise<IterationResponse> => {
    return request.get(`/api/v1/iteration/${iterationId}`)
  },

  createIteration: async (data: IterationCreateRequest): Promise<IterationResponse> => {
    return request.post('/api/v1/iteration/', data)
  },

  updateIteration: async (
    iterationId: number,
    data: IterationUpdateRequest
  ): Promise<IterationResponse> => {
    return request.put(`/api/v1/iteration/${iterationId}`, data)
  },

  deleteIteration: async (
    iterationId: number
  ): Promise<{ code: number; message: string; data: {} }> => {
    return request.delete(`/api/v1/iteration/${iterationId}`)
  },

  addIterationInput: async (
    iterationId: number,
    data: IterationInputRequest
  ): Promise<{ code: number; message: string; data: Record<string, unknown> }> => {
    return request.post(`/api/v1/iteration/${iterationId}/inputs`, data)
  },
}

export const IterationAPI = iterationApi
export default iterationApi
