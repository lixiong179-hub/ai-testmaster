import request from '@/utils/request'

// ============== 项目类型 ==============
export interface Project {
  id: number
  name: string
  description?: string
  project_type: 'web' | 'app'
  status: number
  create_time: string
  update_time: string
}

export interface ProjectCreateRequest {
  name: string
  description?: string
  project_type: 'web' | 'app'
  web_env_configs?: WebEnvConfigs
  device_config?: DeviceConfig
}

export interface ProjectListResponse {
  code: number
  message: string
  data: {
    items: Project[]
    total: number
    page: number
    page_size: number
  }
}

export interface ProjectDetailResponse {
  code: number
  message: string
  data: Project & {
    files: Array<{
      id: number
      file_name: string
      file_type: string
      file_url: string
      file_source: string
      size: number
      upload_time: string
    }>
    web_env_configs?: WebEnvConfigs
    device_config?: DeviceConfig
  }
}

export interface ProjectCreateResponse {
  code: number
  message: string
  data: {
    project_id: number
    name: string
    description: string
    project_type: string
    create_time: string
  }
}

export interface ProjectDeleteResponse {
  code: number
  message: string
  data: {}
}

// ============== Web端环境配置 ==============
export interface WebEnvConfig {
  url?: string
  username?: string
  password?: string
}

export interface WebEnvConfigs {
  test?: WebEnvConfig
  staging?: WebEnvConfig
  prod?: WebEnvConfig
}

// ============== C端设备配置 ==============
export interface DeviceInfo {
  platform?: 'android' | 'ios'
  device_id?: string
  device_name?: string
  app_package?: string
  app_activity?: string
  appium_url?: string
}

export interface DeviceConfig {
  default_device?: DeviceInfo
  devices?: DeviceInfo[]
}

// ============== 项目配置 ==============
export interface ProjectConfig {
  project_type: 'web' | 'app'
  web_env_configs?: WebEnvConfigs
  device_config?: DeviceConfig
}

export interface ProjectConfigResponse {
  code: number
  message: string
  data: ProjectConfig
}

// ============== 项目管理API ==============
const projectApi = {
  // 创建项目
  createProject: async (data: ProjectCreateRequest): Promise<ProjectCreateResponse> => {
    return request.post('/api/v1/project/', data)
  },

  // 获取项目列表
  getProjects: async (params: {
    page?: number
    page_size?: number
  }): Promise<ProjectListResponse> => {
    return request.get('/api/v1/project/list', { params })
  },

  // 获取项目详情
  getProjectDetail: async (projectId: number): Promise<ProjectDetailResponse> => {
    return request.get(`/api/v1/project/${projectId}`)
  },

  // 删除项目
  deleteProject: async (projectId: number): Promise<ProjectDeleteResponse> => {
    return request.delete(`/api/v1/project/${projectId}`)
  },

  // 获取项目配置（Web环境/C端设备）
  getProjectConfig: async (projectId: number): Promise<ProjectConfigResponse> => {
    return request.get(`/api/v1/project/${projectId}/config`)
  },

  // 更新项目配置
  updateProjectConfig: async (
    projectId: number,
    data: ProjectConfig
  ): Promise<ProjectConfigResponse> => {
    return request.put(`/api/v1/project/${projectId}/config`, data)
  },
  // 兼容旧的API名称
  getProjectList: async (params: {
    page?: number
    page_size?: number
  }): Promise<ProjectListResponse> => {
    return projectApi.getProjects(params)
  }
}

export default projectApi
export const ProjectAPI = projectApi
