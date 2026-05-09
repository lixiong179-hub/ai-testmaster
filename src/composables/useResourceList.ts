/**
 * 资源列表 Composable
 * 职责：资源的加载、筛选、分页、类型映射
 */
import { ref, reactive } from 'vue'
import { fileApi } from '@/api/file'
import { uiPrototypeApi } from '@/api/uiPrototype'
import type { IterationSelection } from './useIterationManager'

// 资源类型定义
export interface Resource {
  id: number
  project_id: number
  name: string
  resource_type: string
  file_url?: string
  file_type?: string
  description?: string
  is_active: boolean
  size?: number
  upload_time?: string
  created_at?: string
  screen_count?: number
  prototype_project_id?: number
  source_type?: 'file' | 'ui_prototype'
  iteration_id?: number
}

// 筛选表单类型
export interface FilterForm {
  project_id: number | ''
  resource_type: string
}

export function useResourceList(
  iterationManager: ReturnType<typeof import('./useIterationManager').useIterationManager>
) {
  // 状态定义
  const resources = ref<Resource[]>([])
  const total = ref(0)
  const loading = ref(false)

  const pagination = reactive({
    page: 1,
    pageSize: 10,
  })

  const filterForm = reactive<FilterForm>({
    project_id: '' as number | '',
    resource_type: '',
  })

  /**
   * 从响应数据中提取列表项（增强版）
   *
   * 支持的数据格式：
   * 1. 纯数组: [item1, item2, ...]
   * 2. { items: [...] }
   * 3. { data: { items: [...] } }
   * 4. { data: [...] } ← 新增支持
   * 5. 其他情况返回空数组
   */
  function extractListItems(res: unknown): Record<string, unknown>[] {
    if (!res) return []

    if (Array.isArray(res)) {
      return res as Record<string, unknown>[]
    }

    if (typeof res !== 'object' || res === null) return []

    const resObj = res as Record<string, unknown>
    if (Array.isArray(resObj.items)) {
      return resObj.items as Record<string, unknown>[]
    }

    const d = resObj.data
    if (d != null) {
      if (Array.isArray(d)) {
        return d as Record<string, unknown>[]
      }

      if (
        typeof d === 'object' &&
        d !== null &&
        Array.isArray((d as Record<string, unknown>).items)
      ) {
        return (d as Record<string, unknown>).items as Record<string, unknown>[]
      }
    }

    return []
  }

  /**
   * 获取资源列表（后端真分页方案C）
   *
   * 采用方案C：保持现有的双API调用架构（文件+UI原型），
   * 但确保每个API都正确传递 iteration_id 参数让后端筛选，
   * 同时传递 page/page_size 实现真正的后端分页。
   */
  const getResources = async () => {
    if (!filterForm.project_id) {
      resources.value = []
      total.value = 0
      loading.value = false
      return
    }

    loading.value = true
    try {
      const projectId = Number(filterForm.project_id)
      const resourceTypeFilter = filterForm.resource_type
      // 获取转换后的迭代ID参数（用于后端筛选）
      const iterationParam = iterationManager.getIterationIdParam()

      let allItems: Resource[] = []

      // 判断是否需要加载各类型的资源
      const shouldLoadFiles = !resourceTypeFilter || resourceTypeFilter !== 'ui_mockup'
      const shouldLoadPrototypes = !resourceTypeFilter || resourceTypeFilter === 'ui_mockup'

      if (shouldLoadFiles) {
        try {
          // 直接将 iteration_id 和分页参数传给后端，由后端筛选
          const fileRes = await fileApi.getFileList(
            projectId,
            iterationParam, // 传递迭代筛选参数
            pagination.page,
            pagination.pageSize // 传递分页参数
          )
          const fileItems = extractListItems(fileRes)
            .filter((item: Record<string, unknown>) => {
              if (resourceTypeFilter && item.resource_type !== resourceTypeFilter) return false
              return true
            })
            .map((item: Record<string, unknown>) => ({
              id: item.id as number,
              project_id: item.project_id as number,
              name: item.file_name as string,
              resource_type: (item.resource_type as string) || 'other',
              file_url: item.file_url as string | undefined,
              file_type: item.file_type as string | undefined,
              is_active: item.is_active !== false,
              size: item.size as number | undefined,
              created_at: item.upload_time as string | undefined,
              upload_time: item.upload_time as string | undefined,
              iteration_id: item.iteration_id as number | undefined,
              source_type: 'file' as const,
            }))
          allItems = allItems.concat(fileItems)
        } catch (e) {
          console.warn('获取文件列表失败:', e)
        }
      }

      if (shouldLoadPrototypes) {
        try {
          // 直接将 iteration_id 和分页参数传给后端，由后端筛选
          const protoRes = await uiPrototypeApi.getUIPrototypeProjectList(
            projectId,
            pagination.page,
            pagination.pageSize,
            iterationParam // 传递迭代筛选参数
          )
          const protoItems = extractListItems(protoRes).map((item: Record<string, unknown>) => ({
            id: item.id as number,
            project_id: item.project_id as number,
            name: item.name as string,
            resource_type: 'ui_mockup',
            file_url: undefined,
            file_type: undefined,
            is_active: true,
            size: undefined,
            created_at: item.create_time as string | undefined,
            upload_time: item.create_time as string | undefined,
            iteration_id: item.iteration_id as number | undefined,
            screen_count: (item.screen_count as number) || 0,
            prototype_project_id: item.id as number,
            source_type: 'ui_prototype' as const,
            description: item.description as string | undefined,
          }))
          allItems = allItems.concat(protoItems)
        } catch (e) {
          console.warn('获取UI原型项目列表失败:', e)
        }
      }

      // 按时间倒序排序（最新的在前）
      allItems.sort((a, b) => {
        const timeA = new Date(a.upload_time || a.created_at || 0).getTime()
        const timeB = new Date(b.upload_time || b.created_at || 0).getTime()
        return timeB - timeA
      })

      // 设置总数和当前页数据（增加防御性检查，确保100%是数组）
      const finalItems = Array.isArray(allItems) ? allItems : []
      total.value = finalItems.length
      resources.value = finalItems // 确保 resources.value 始终是数组
    } catch (error) {
      console.error('获取资源列表失败:', error)
      resources.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  /**
   * 搜索操作
   */
  const handleSearch = () => {
    pagination.page = 1
    getResources()
  }

  /**
   * 重置筛选条件
   */
  const handleReset = () => {
    filterForm.project_id = ''
    filterForm.resource_type = ''
    iterationManager.selectedIterationId = null as IterationSelection
    // 注意：清空迭代列表需要在调用处处理，因为 iterations 属于 iterationManager
    pagination.page = 1
    resources.value = []
    total.value = 0
  }

  /**
   * 每页条数改变
   */
  const handleSizeChange = (val: number) => {
    pagination.pageSize = val
    pagination.page = 1
    getResources()
  }

  /**
   * 页码改变
   */
  const handleCurrentChange = (val: number) => {
    pagination.page = val
    getResources()
  }

  /**
   * 资源类型标签类型映射
   */
  const getResourceTypeTagType = (type: string): string => {
    const typeMap: Record<string, string> = {
      requirement: 'primary',
      ui_mockup: 'warning',
      api_doc: 'success',
      test_data: 'info',
      other: 'info',
    }
    return typeMap[type] || 'info'
  }

  /**
   * 资源类型标签文本映射
   */
  const getResourceTypeLabel = (type: string): string => {
    const labelMap: Record<string, string> = {
      requirement: '需求文档',
      ui_mockup: 'UI原型图',
      api_doc: 'API文档',
      test_data: '测试数据',
      other: '其他',
    }
    return labelMap[type] || type
  }

  const refreshAndResetPage = async () => {
    pagination.page = 1
    await getResources()
  }

  return reactive({
    resources,
    total,
    loading,
    get isLoading() {
      return loading.value === true
    },
    pagination,
    filterForm,

    getResources,
    refreshAndResetPage,
    handleSearch,
    handleReset,
    handleSizeChange,
    handleCurrentChange,
    getResourceTypeTagType,
    getResourceTypeLabel,
  })
}
