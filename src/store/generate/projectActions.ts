import { ElMessage } from 'element-plus'
import { fileApi } from '@/api/file'
import caseApi from '@/api/case'
import ProjectAPI, { type ProjectListResponse } from '@/api/project'
import type { Project } from '@/api/project'
import { useFlowSortStore } from '@/store/flowSort'
import { extractListItems } from './types'
import type { GenerateState } from './state'
import type { StoreActions } from './types'

const HISTORY_CASE_LIFECYCLE_STATUSES = [
  'draft',
  'active',
  'pending_review',
  'needs_modify',
  'locator_broken',
  'deprecated',
].join(',')

export function createProjectActions(state: GenerateState, getActions: () => StoreActions) {
  const getProjects = async (forceReload: boolean = false) => {
    if (state.projectsLoaded.value && !forceReload && state.projects.value.length > 0) {
      return
    }
    state.projectsLoading.value = true
    try {
      const response: ProjectListResponse = await ProjectAPI.getProjects({
        page: 1,
        page_size: 1000,
      })
      if (response?.data?.items) {
        state.projects.value = response.data.items.filter((p: Project) => p.name !== '默认项目')
        state.projectsLoaded.value = true
      }
    } catch (error) {
      console.error('获取项目列表失败:', error)
    } finally {
      state.projectsLoading.value = false
    }
  }

  const loadProjectFiles = async () => {
    try {
      const response = await fileApi.getFileList(state.formData.project_id as number)
      const items = extractListItems(response) as import('@/api/file').ProjectFile[]
      state.requirementFiles.value = items.filter((f) => f.resource_type === 'requirement')
      state.uiFiles.value = items.filter((f) => f.resource_type === 'ui_mockup')
    } catch (error) {
      console.error('获取文件列表失败:', error)
    }
  }

  const loadProjectCases = async () => {
    if (!state.formData.project_id) {
      state.projectCases.value = []
      return
    }
    state.isLoadingProjectCases.value = true
    try {
      const response = await caseApi.getCaseList({
        project_id: state.formData.project_id as number,
        lifecycle_status: HISTORY_CASE_LIFECYCLE_STATUSES,
        page_size: 500,
      })
      state.projectCases.value = response?.data?.items || []
    } catch (e) {
      console.warn('加载项目用例失败:', e)
      state.projectCases.value = []
    } finally {
      state.isLoadingProjectCases.value = false
    }
  }

  const handleProjectChange = () => {
    state.formData.requirement_file_ids = []
    state.formData.ui_file_ids = []
    state.formData.ui_screen_ids = []
    state.formData.test_point_ids = []
    state.contextPreview.value = null
    state.lastContext.value = {}
    state.generatedCases.value = []
    state.currentCaseIndex.value = -1
    state.selectedUiPrototypeProjectId.value = ''
    state.uiPrototypeProjects.value = []
    state.uiScreens.value = []
    const flowSortStore = useFlowSortStore()
    flowSortStore.reset()
    if (state.formData.project_id) {
      flowSortStore.setProjectId(state.formData.project_id as number)
    }
    state.selectedHistoryCaseIds.value = []
    state._historyCaseUserCleared.value = false
    state.projectCases.value = []
    getActions().handleSourceFileChange()
    getActions().loadProjectFiles()
    getActions().loadUIPrototypeProjects()
    getActions().loadProjectCases()
    getActions().loadTestPoints(1)
  }

  const handleProjectFocus = () => {
    if (!state.projectsLoaded.value || state.projects.value.length === 0) {
      getProjects()
    }
  }

  const extractFileContent = async () => {
    if (
      state.formData.requirement_file_ids.length === 0 &&
      state.formData.ui_file_ids.length === 0
    ) {
      ElMessage.warning('请先选择文件')
      return
    }
    const allFileIds = [...state.formData.requirement_file_ids, ...state.formData.ui_file_ids]
    try {
      const response = await fileApi.extractContent({
        file_ids: allFileIds,
        project_id: Number(state.formData.project_id),
      })
      const resData = (response as any)?.data ?? response
      if (resData?.code === 200) {
        await getActions().loadProjectFiles()
        const data = resData.data as { success?: number; failed?: number }
        state.contextPreview.value = {
          title: `内容提取完成：成功 ${data?.success || 0} 个，失败 ${data?.failed || 0} 个`,
          type: (data?.failed || 0) > 0 ? 'warning' : 'success',
          requirement: `选择了 ${allFileIds.length} 个文件`,
          ui:
            state.formData.ui_screen_ids.length > 0
              ? `${state.formData.ui_screen_ids.length} 个屏幕`
              : state.formData.ui_file_ids.length > 0
                ? `${state.formData.ui_file_ids.length} 个文件`
                : '',
          uiSpecs: (state.lastContext.value as Record<string, unknown[]>)?.ui_specs?.length || 0,
        }
        ElMessage.success('文件内容提取完成')
      } else {
        ElMessage.error(resData?.msg || resData?.message || '提取内容失败')
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      ElMessage.error(err.response?.data?.detail || '提取内容失败')
    }
  }

  return {
    getProjects,
    loadProjectFiles,
    loadProjectCases,
    handleProjectChange,
    handleProjectFocus,
    extractFileContent,
  }
}
