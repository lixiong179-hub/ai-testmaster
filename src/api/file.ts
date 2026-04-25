import request from '@/utils/request'

// 文件类型定义
export interface ProjectFile {
  id: number
  project_id: number
  iteration_id?: number
  file_name: string
  file_type: string
  file_url: string
  file_source: string
  resource_type?: string // 资源类型：requirement, ui_mockup, api_doc, test_data, other
  extract_status?: string // 提取状态：completed, processing, pending, failed
  is_active?: boolean // 是否启用
  description?: string // 描述
  size?: number
  upload_time: string
}

export interface UrlSubmitRequest {
  project_id: number
  url: string
  file_type: string
  resource_type?: string
  description?: string
}

export interface FileListResponse {
  code: number
  message: string
  data: {
    items: ProjectFile[]
    total: number
  }
}

export interface FileUploadResponse {
  code: number
  message: string
  data: {
    file_id: number
    file_name: string
    file_type: string
    file_url: string
    size: number
    upload_time: string
  }
}

export interface UrlSubmitResponse {
  code: number
  message: string
  data: {
    file_id: number
    file_name: string
    file_type: string
    file_url: string
    upload_time: string
  }
}

export interface FileBatchUploadResponse {
  code: number
  message: string
  data: {
    uploaded_files: ProjectFile[]
    failed_files: { file_name: string; reason: string }[]
    success_count: number
    fail_count: number
  }
}

export interface FileDeleteResponse {
  code: number
  message: string
  data: {}
}

export interface FileUpdateRequest {
  resource_type: string
  description?: string
  iteration_id?: number | null
}

export interface FileUpdateResponse {
  code: number
  message: string
  data?: ProjectFile
}

// 文件管理API
export const fileApi = {
  // 上传文件
  uploadFile: async (
    projectId: number,
    file: File,
    resourceType: string = 'other',
    description: string = '',
    iterationId?: number
  ): Promise<FileUploadResponse> => {
    const formData = new FormData()
    formData.append('project_id', projectId.toString())
    formData.append('file', file)
    formData.append('resource_type', resourceType)
    formData.append('description', description)
    if (iterationId !== undefined && iterationId !== null) {
      formData.append('iteration_id', iterationId.toString())
    }

    return request.post('/api/v1/file/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  // 提交URL
  submitUrl: async (data: UrlSubmitRequest): Promise<UrlSubmitResponse> => {
    return request.post('/api/v1/file/submit-url', data)
  },

  // 获取所有文件列表
  getAllFiles: async (iterationId?: number): Promise<FileListResponse> => {
    const params: Record<string, string | number> = {}
    if (iterationId !== undefined && iterationId !== null) {
      params.iteration_id = iterationId
    }
    return request.get('/api/v1/file/list', { params })
  },

  // 获取文件列表（支持后端分页和迭代筛选）
  getFileList: async (
    projectId: number,
    iterationId?: number,
    page: number = 1,
    pageSize: number = 100
  ): Promise<FileListResponse> => {
    const params: Record<string, string | number> = { page, page_size: pageSize }
    if (iterationId !== undefined && iterationId !== null) {
      params.iteration_id = iterationId
    }
    return request.get(`/api/v1/file/list/${projectId}`, { params })
  },

  // 批量上传文件（主要用于UI原型图批量上传）
  batchUploadFiles: async (
    projectId: number,
    files: File[],
    resourceType: string = 'ui_mockup',
    description: string = '',
    name: string = '',
    iterationId?: number
  ): Promise<FileBatchUploadResponse> => {
    const formData = new FormData()
    formData.append('project_id', projectId.toString())
    formData.append('resource_type', resourceType)
    formData.append('description', description)
    if (name) {
      formData.append('name', name)
    }
    if (iterationId !== undefined && iterationId !== null) {
      formData.append('iteration_id', iterationId.toString())
    }
    files.forEach((file) => {
      formData.append('files', file)
    })
    return request.post('/api/v1/file/batch-upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  // 更新文件信息
  updateFile: async (fileId: number, data: FileUpdateRequest): Promise<FileUpdateResponse> => {
    return request.put(`/api/v1/file/${fileId}`, data)
  },

  // 删除文件
  deleteFile: async (fileId: number, projectId: number): Promise<FileDeleteResponse> => {
    return request.delete(`/api/v1/file/${fileId}`, {
      params: {
        project_id: projectId,
      },
    })
  },
}

// 保持向后兼容
export const FileAPI = fileApi
export default fileApi
