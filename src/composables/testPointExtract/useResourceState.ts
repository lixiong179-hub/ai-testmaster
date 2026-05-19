import { computed } from 'vue'
import request from '@/utils/request'
import type { ExtractSharedState, ProjectItem, ResourceRow } from './types'

export function useResourceState(state: ExtractSharedState) {
  const selectedProjectInfo = computed(() => {
    if (!state.formData.project_id) return null
    return state.projects.value.find((p) => p.id === state.formData.project_id) || null
  })

  const currentProjectId = computed(() => {
    return state.formData.project_id ? Number(state.formData.project_id) : 0
  })

  const resourceRows = computed<ResourceRow[]>(() => {
    return state.files.value.map((f) => ({
      source: 'file' as const,
      id: f.id,
      project_id: f.project_id,
      display_name: f.file_name,
      resource_type: f.resource_type || 'other',
      type_label: getResourceTypeLabel(f.resource_type || 'other'),
      size_text: formatFileSize(f.size),
      time_text: f.upload_time,
    }))
  })

  const filteredResourceRows = computed(() => {
    if (!state.resourceTypeFilter.value) return resourceRows.value
    return resourceRows.value.filter((r) => r.resource_type === state.resourceTypeFilter.value)
  })

  function formatFileSize(size: number): string {
    if (size < 1024) {
      return size + ' B'
    } else if (size < 1024 * 1024) {
      return (size / 1024).toFixed(2) + ' KB'
    } else {
      return (size / (1024 * 1024)).toFixed(2) + ' MB'
    }
  }

  function getResourceTypeLabel(type: string): string {
    const labelMap: Record<string, string> = {
      requirement: '需求文档',
      ui_mockup: 'UI原型图',
      api_doc: 'API文档',
      test_data: '测试数据',
      other: '其他',
    }
    return labelMap[type] || type
  }

  function getResourceTypeTagType(type: string): string {
    const tagMap: Record<string, string> = {
      requirement: 'primary',
      ui_mockup: 'warning',
      api_doc: 'success',
      test_data: 'info',
      other: 'info',
    }
    return tagMap[type] || 'info'
  }

  function getResourceIcon(type: string): 'Document' | 'Picture' | 'DocumentCopy' | 'Files' {
    const iconMap: Record<string, 'Document' | 'Picture' | 'DocumentCopy' | 'Files'> = {
      requirement: 'Document',
      ui_mockup: 'Picture',
      api_doc: 'DocumentCopy',
      test_data: 'Files',
      other: 'Document',
    }
    return iconMap[type] || 'Document'
  }

  function getResourceTypeCount(type: string): number {
    return state.files.value.filter((f) => f.resource_type === type).length
  }

  function getResourceTypePercentage(type: string): number {
    const total = state.files.value.length
    if (total === 0) return 0
    return Math.round((getResourceTypeCount(type) / total) * 100)
  }

  async function getProjects(): Promise<void> {
    try {
      const response = await request.get('/api/v1/project/list')
      if (response && response.data && response.data.items) {
        state.projects.value = response.data.items.filter(
          (project: ProjectItem) => project.name !== '默认项目'
        )
      } else {
        state.projects.value = []
      }
    } catch (error) {
      console.error('获取项目列表失败:', error)
      state.projects.value = []
    }
  }

  async function loadResources(projectId: number): Promise<void> {
    try {
      const fileRes = await request.get(`/api/v1/file/list/${projectId}`)
      if (fileRes && fileRes.data && fileRes.data.items) {
        state.files.value = fileRes.data.items
      } else {
        state.files.value = []
      }
    } catch (error) {
      console.error('获取文件列表失败:', error)
      state.files.value = []
    }
  }

  function handleResourceSelect(row: ResourceRow): void {
    state.selectedResource.value = row
  }

  return {
    selectedProjectInfo,
    currentProjectId,
    resourceRows,
    filteredResourceRows,
    formatFileSize,
    getResourceTypeLabel,
    getResourceTypeTagType,
    getResourceIcon,
    getResourceTypeCount,
    getResourceTypePercentage,
    getProjects,
    loadResources,
    handleResourceSelect,
  }
}
