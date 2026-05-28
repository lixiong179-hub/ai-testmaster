import { type InjectionKey, inject, provide, ref, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import ProjectAPI from '@/api/project'
import { useIterationManager, type SafeIteration } from '@/composables/useIterationManager'
import { useResourceList } from '@/composables/useResourceList'
import { useResourceUpload } from '@/composables/useResourceUpload'
import { useResourceOperations } from '@/composables/useResourceOperations'
import {
  RESOURCE_TYPE_OPTIONS as _RESOURCE_TYPE_OPTIONS,
  ITERATION_STATUS_OPTIONS as _ITERATION_STATUS_OPTIONS,
  RESOURCE_CONFIG as _RESOURCE_CONFIG,
} from '@/constants/resource'

export {
  _RESOURCE_TYPE_OPTIONS as RESOURCE_TYPE_OPTIONS,
  _ITERATION_STATUS_OPTIONS as ITERATION_STATUS_OPTIONS,
  _RESOURCE_CONFIG as RESOURCE_CONFIG,
}

interface Project {
  id: number
  name: string
}
interface Resource {
  id: number
  project_id: number
  name: string
  resource_type: string
  source_type?: 'file' | 'ui_prototype'
  screen_count?: number
  is_active: boolean
  upload_time?: string
  created_at?: string
  iteration_id?: number
  prototype_project_id?: number
}

export type ResourceManageContext = ReturnType<typeof createResourceManageContext>
export const RESOURCE_MANAGE_KEY: InjectionKey<ResourceManageContext> = Symbol('resourceManage')

function createResourceManageContext() {
  const iterationManager = useIterationManager()
  const resourceList = useResourceList(iterationManager)
  const resourceUpload = useResourceUpload(iterationManager, () => {
    resourceList.pagination.page = 1
    resourceList.getResources()
  })
  const resourceOperations = useResourceOperations(iterationManager, () => {
    resourceList.pagination.page = 1
    resourceList.getResources()
  })

  const iterationFormLocalRef = ref()
  const fileFormLocalRef = ref()
  const uploaderRef = ref<any>(null)
  const projects = ref<Project[]>([])

  const safeIterationsArray = computed(() => iterationManager.safeIterations as SafeIteration[])
  const validIterationsForSelectArray = computed(
    () => iterationManager.validIterationsForSelect as SafeIteration[]
  )
  const getIterationStats = (id: number) => iterationManager.getIterationStatsById(id)

  const isFileSubmitting = computed(() => {
    if (resourceUpload.fileDialogMode === 'edit') return resourceUpload.isSubmitting
    return uploaderRef.value?.uploading ?? false
  })

  const getProjects = async () => {
    try {
      const response = await ProjectAPI.getProjects({ page: 1, page_size: 100 })
      if (response?.data?.items)
        projects.value = response.data.items.filter((p: Project) => p.name !== '默认项目')
      else projects.value = []
    } catch (error) {
      console.error('获取项目列表失败:', error)
      projects.value = []
    }
  }

  const handleSelectIterationAndRefresh = async (iterationId: number | null) => {
    try {
      iterationManager.handleSelectIteration(iterationId)
      resourceList.pagination.page = 1
      await resourceList.getResources()
    } catch (error) {
      console.error('切换迭代失败:', error)
      ElMessage.error('切换迭代失败，请重试')
    }
  }

  const handleAddIterationWrapper = () => {
    iterationManager.handleAddIteration(Number(resourceList.filterForm.project_id))
  }

  const handleAddFileWrapper = () => {
    if (!resourceList.filterForm.project_id) {
      ElMessage.warning('请先选择项目')
      return
    }
    resourceUpload.resetFileForm()
    resourceUpload.fileDialogMode = 'add'
    resourceUpload.fileFormData.project_id = resourceList.filterForm.project_id as number
    if (
      iterationManager.selectedIterationId !== null &&
      iterationManager.selectedIterationId !== 0
    ) {
      resourceUpload.fileFormData.iteration_id = iterationManager.selectedIterationId
    } else {
      resourceUpload.fileFormData.iteration_id = null
    }
    resourceUpload.fileDialogVisible = true
    nextTick(() => {
      uploaderRef.value?.clearFiles()
    })
  }

  const handleFileSubmitWrapper = async () => {
    if (resourceUpload.fileDialogMode === 'edit') {
      if (!fileFormLocalRef.value) {
        ElMessage.error('表单初始化失败，请刷新页面重试')
        return
      }
      await resourceUpload.handleFileSubmit(fileFormLocalRef.value)
      return
    }
    if (!uploaderRef.value) {
      ElMessage.error('上传组件初始化失败，请刷新页面重试')
      return
    }
    if (uploaderRef.value.fileCount === 0) {
      ElMessage.warning('请选择文件')
      return
    }
    await uploaderRef.value.upload()
  }

  const handleEditWrapper = (row: Resource) => {
    const shouldOpenDialog = resourceOperations.handleEditNavigation(row)
    if (shouldOpenDialog) resourceUpload.handleEdit(row)
  }

  const handleBatchUploadSuccess = () => {
    resourceUpload.fileDialogVisible = false
    resourceList.pagination.page = 1
    resourceList.getResources()
  }

  const handleBatchUploadError = () => {}

  const handleIterationCommandWrapper = async (command: string, iteration: SafeIteration) => {
    const needRefresh = await iterationManager.handleIterationCommand(command, iteration as any)
    if (needRefresh) {
      resourceList.pagination.page = 1
      await iterationManager.loadIterations(Number(resourceList.filterForm.project_id))
      await resourceList.getResources()
    }
  }

  const handleIterationSubmitWrapper = async () => {
    if (!iterationFormLocalRef.value) {
      ElMessage.error('表单初始化失败，请刷新页面重试')
      return
    }
    try {
      await iterationFormLocalRef.value.validate()
    } catch {
      return
    }
    const needRefresh = await iterationManager.handleIterationSubmit(iterationFormLocalRef.value)
    if (needRefresh) {
      resourceList.pagination.page = 1
      iterationManager.loadIterations(Number(resourceList.filterForm.project_id))
      resourceList.getResources()
    }
  }

  const handleReset = async () => {
    resourceList.handleReset()
    if (!resourceList.filterForm.project_id) await iterationManager.loadIterations(0)
  }

  watch(
    () => resourceList.filterForm.project_id,
    async () => {
      resourceList.pagination.page = 1
      iterationManager.selectedIterationId = null
      if (resourceList.filterForm.project_id)
        await iterationManager.loadIterations(Number(resourceList.filterForm.project_id))
      else await iterationManager.loadIterations(0)
      await resourceList.getResources()
    }
  )

  let isInitializing = true
  let initTimer: ReturnType<typeof setTimeout> | null = null

  const init = async () => {
    iterationManager.iterationDialogVisible = false
    resourceUpload.fileDialogVisible = false
    try {
      await getProjects()
      if (!resourceList.filterForm.project_id && projects.value.length > 0)
        resourceList.filterForm.project_id = projects.value[0].id
      if (resourceList.filterForm.project_id) {
        await iterationManager.loadIterations(Number(resourceList.filterForm.project_id))
        await resourceList.getResources()
      }
    } catch (error) {
      console.error('页面初始化失败:', error)
      ElMessage.error('页面初始化失败，请刷新重试')
    }
    await nextTick()
    iterationManager.iterationDialogVisible = false
    resourceUpload.fileDialogVisible = false
    initTimer = setTimeout(() => {
      iterationManager.iterationDialogVisible = false
      resourceUpload.fileDialogVisible = false
      isInitializing = false
    }, 500)
  }

  const cleanup = () => {
    if (initTimer) {
      clearTimeout(initTimer)
      initTimer = null
    }
  }

  watch(
    () => iterationManager.iterationDialogVisible,
    (v) => {
      if (isInitializing && v)
        nextTick(() => {
          iterationManager.iterationDialogVisible = false
        })
    }
  )
  watch(
    () => resourceUpload.fileDialogVisible,
    (v) => {
      if (isInitializing && v)
        nextTick(() => {
          resourceUpload.fileDialogVisible = false
        })
    }
  )

  return {
    iterationManager,
    resourceList,
    resourceUpload,
    resourceOperations,
    iterationFormLocalRef,
    fileFormLocalRef,
    uploaderRef,
    projects,
    safeIterationsArray,
    validIterationsForSelectArray,
    getIterationStats,
    isFileSubmitting,
    handleSelectIterationAndRefresh,
    handleAddIterationWrapper,
    handleAddFileWrapper,
    handleFileSubmitWrapper,
    handleEditWrapper,
    handleBatchUploadSuccess,
    handleBatchUploadError,
    handleIterationCommandWrapper,
    handleIterationSubmitWrapper,
    handleReset,
    init,
    cleanup,
    RESOURCE_TYPE_OPTIONS: _RESOURCE_TYPE_OPTIONS,
    ITERATION_STATUS_OPTIONS: _ITERATION_STATUS_OPTIONS,
    RESOURCE_CONFIG: _RESOURCE_CONFIG,
  }
}

export function provideResourceManage() {
  const ctx = createResourceManageContext()
  provide(RESOURCE_MANAGE_KEY, ctx)
  return ctx
}

export function useResourceManage() {
  const ctx = inject(RESOURCE_MANAGE_KEY)
  if (!ctx) throw new Error('ResourceManage context not provided')
  return ctx
}
