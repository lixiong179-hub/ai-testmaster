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
  status?: string
  start_date?: string
  end_date?: string
}

export interface IterationUpdateRequest {
  name?: string
  version?: string
  description?: string
  status?: string
  start_date?: string
  end_date?: string
}

export interface IterationResponse {
  code: number
  message: string
  data: Iteration
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
}

export const IterationAPI = iterationApi
export default iterationApi
