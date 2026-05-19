import { type Ref } from 'vue'
import type { Router, RouteLocationNormalizedLoaded } from 'vue-router'
import type { TableInstance } from 'element-plus'

export interface TestPointItem {
  id: number
  module: string
  function?: string
  point: string
  priority: number
  ai_prompt?: string
  create_time?: string
  _raw?: Record<string, unknown>
}

export interface ProjectItem {
  id: number
  name: string
}

export interface FileItem {
  id: number
  project_id: number
  file_name: string
  file_url: string
  file_type: string
  size: number
  upload_time: string
  file_source: string
  resource_type?: string
}

export interface ResourceRow {
  source: 'file'
  id: number
  project_id: number
  display_name: string
  resource_type: string
  type_label: string
  size_text: string
  time_text: string
}

export interface TestPointListResponse {
  code: number
  data?: {
    items: TestPointItem[]
    total: number
  }
  message?: string
}

export const PROGRESS_PHASES = [
  { end: 20, text: '正在读取文件内容...' },
  { end: 40, text: '正在解析文档结构...' },
  { end: 65, text: 'AI 正在分析需求并提取测试点...' },
  { end: 85, text: '正在整理测试点数据...' },
]

export interface ExtractSharedState {
  router: Router
  route: RouteLocationNormalizedLoaded
  currentStep: Ref<number>
  formData: { project_id: number | '' }
  projects: Ref<ProjectItem[]>
  files: Ref<FileItem[]>
  selectedResource: Ref<ResourceRow | null>
  testPoints: Ref<TestPointItem[]>
  extracting: Ref<boolean>
  saving: Ref<boolean>
  batchDeleting: Ref<boolean>
  deleting: Ref<boolean>
  savedFromDb: Ref<boolean>
  loadingTestPoints: Ref<boolean>
  selectedRows: Ref<TestPointItem[]>
  testPointTable: Ref<TableInstance | undefined>
  currentPage: Ref<number>
  pageSize: Ref<number>
  dbTotal: Ref<number>
  progress: Ref<number>
  progressText: Ref<string>
  progressInterval: Ref<ReturnType<typeof setInterval> | null>
  errorMessage: Ref<string>
  dialogVisible: Ref<boolean>
  resourceTypeFilter: Ref<string>
  editForm: TestPointItem
  editingIndex: Ref<number>
  updating: Ref<boolean>
}
