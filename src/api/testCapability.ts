import request from '@/utils/request'

export interface TestCapabilityResponse {
  id: number
  project_id: number
  key: string
  title: string
  description: string | null
  status: string
  created_at: string
  updated_at: string | null
}

export interface TestCapabilityCreateRequest {
  project_id: number
  key: string
  title: string
  description?: string
  status?: string
}

export interface TestCapabilityUpdateRequest {
  key?: string
  title?: string
  description?: string
  status?: string
}

export interface TestCapabilityListParams {
  project_id: number
  status?: string
}

export const testCapabilityApi = {
  getList: (params: TestCapabilityListParams) => {
    return request.get<TestCapabilityResponse[]>('/api/v1/test-capability/', { params })
  },

  create: (data: TestCapabilityCreateRequest) => {
    return request.post<TestCapabilityResponse>('/api/v1/test-capability/', data)
  },

  getDetail: (capabilityId: number) => {
    return request.get<TestCapabilityResponse>(`/api/v1/test-capability/${capabilityId}`)
  },

  update: (capabilityId: number, data: TestCapabilityUpdateRequest) => {
    return request.put<TestCapabilityResponse>(`/api/v1/test-capability/${capabilityId}`, data)
  },

  delete: (capabilityId: number) => {
    return request.delete(`/api/v1/test-capability/${capabilityId}`)
  },
}
