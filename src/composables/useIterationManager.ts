import { ref, computed, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { iterationApi, type Iteration } from '@/api/iteration'
import { fileApi } from '@/api/file'
import { uiPrototypeApi } from '@/api/uiPrototype'
import { useIterationForm } from './useIterationForm'

export type IterationSelection = null | 0 | number

export type SafeIteration = {
  id: number
  project_id: number
  name: string
  version: string
  description: string
  status: string
  start_date: string | null
  end_date: string | null
  create_time: string
  update_time: string
}

export function useIterationManager() {
  const iterations = ref<Iteration[]>([])
  const selectedIterationId = ref<IterationSelection>(null)
  const iterationStats = ref<Record<number, { files: number; prototypes: number }>>({})

  const safeIterations = computed<SafeIteration[]>(() => {
    try {
      const arr = Array.isArray(iterations.value) ? iterations.value : []
      return arr.filter((it: Iteration) => it && typeof it === 'object' && it.id != null && Number.isInteger(it.id))
        .map((it: Iteration) => ({
          id: it.id, project_id: it.project_id, name: it.name || '未命名迭代',
          version: it.version || 'v1.0', description: it.description || '', status: it.status || 'planning',
          start_date: it.start_date || null, end_date: it.end_date || null,
          create_time: it.create_time || new Date().toISOString(), update_time: it.update_time || new Date().toISOString(),
        }))
    } catch { return [] }
  })

  const validIterationsForSelect = computed<SafeIteration[]>(() => safeIterations.value.filter((it) => it.id))

  const formManager = useIterationForm()

  function extractListItems(res: unknown): Record<string, unknown>[] {
    if (!res || typeof res !== 'object') return []
    if (Array.isArray(res)) return res as Record<string, unknown>[]
    const resObj = res as Record<string, unknown>
    if (Array.isArray(resObj.items)) return resObj.items as Record<string, unknown>[]
    const d = resObj.data
    if (d && typeof d === 'object' && Array.isArray((d as Record<string, unknown>).items)) return (d as Record<string, unknown>).items as Record<string, unknown>[]
    return []
  }

  const loadIterations = async (projectId: number) => {
    if (!projectId) { iterations.value = []; iterationStats.value = {}; return }
    try {
      const response = await iterationApi.getIterations(projectId)
      const items = extractListItems(response)
      iterations.value = items as unknown as Iteration[]
      await Promise.all((items as unknown as Iteration[]).map(async (it: Iteration) => {
        try {
          const [fileRes, protoRes] = await Promise.all([fileApi.getFileList(projectId, it.id, 1, 1), uiPrototypeApi.getUIPrototypeProjectList(projectId, 1, 1, it.id)])
          const fileData = fileRes as unknown as Record<string, unknown>
          const fileResponseData = fileData?.data as Record<string, unknown> | undefined
          const fileTotal = (fileResponseData?.total as number) || (extractListItems(fileRes).length > 0 ? (fileResponseData?.total as number) || 0 : 0)
          const protoData = protoRes as unknown as Record<string, unknown>
          const protoResponseData = protoData?.data as Record<string, unknown> | undefined
          const protoTotal = (protoResponseData?.total as number) || (extractListItems(protoRes).length > 0 ? (protoResponseData?.total as number) || 0 : 0)
          iterationStats.value[it.id] = { files: fileTotal, prototypes: protoTotal }
        } catch (e) { console.warn(`获取迭代 ${it.name} 统计失败:`, e); iterationStats.value[it.id] = { files: 0, prototypes: 0 } }
      }))
    } catch (error) { console.error('获取迭代列表失败:', error); iterations.value = []; iterationStats.value = {} }
  }

  const handleSelectIteration = (iterationId: IterationSelection) => { selectedIterationId.value = iterationId }

  const getIterationIdParam = (): number | undefined => {
    if (selectedIterationId.value === null) return undefined
    if (selectedIterationId.value === 0) return 0
    return selectedIterationId.value
  }

  const handleDeleteIteration = async (iteration: Iteration): Promise<boolean> => {
    try {
      await ElMessageBox.confirm('删除迭代将同时删除其下所有需求文档和UI原型图，确定要删除吗？', '删除确认', { type: 'warning' })
      await iterationApi.deleteIteration(iteration.id)
      ElMessage.success(`迭代 "${iteration.name}" 及其下的所有资源已删除`)
      if (selectedIterationId.value === iteration.id) selectedIterationId.value = null
      return true
    } catch (error: unknown) { if (error !== 'cancel') formManager.showError('删除迭代', error); return false }
  }

  const handleIterationCommand = async (command: string, iteration: Iteration): Promise<boolean> => {
    if (command === 'edit') { formManager.handleEditIteration(iteration); return false }
    else if (command === 'delete') return await handleDeleteIteration(iteration)
    return false
  }

  const getIterationStatusType = (status: string): string => { const m: Record<string, string> = { planning: 'info', active: 'success', completed: '', archived: 'warning' }; return m[status] || 'info' }
  const getIterationStatusText = (status: string): string => { const m: Record<string, string> = { planning: '规划中', active: '进行中', completed: '已完成', archived: '已归档' }; return m[status] || status }
  const getCurrentIterationTitle = (): string => {
    if (selectedIterationId.value === null) return '全部资源'
    if (selectedIterationId.value === 0) return '未分类资源'
    const iteration = iterations.value.find((it) => it.id === selectedIterationId.value)
    return iteration ? `${iteration.name} (${iteration.version})` : '资源列表'
  }
  const getIterationNameById = (id: number): string => { if (id === 0) return '未分类'; const it = iterations.value.find((i) => i.id === id); return it ? it.name : '未知迭代' }
  const getIterationStatsById = (id: number): { files: number; prototypes: number } => { const stats = iterationStats.value?.[id]; return { files: stats?.files ?? 0, prototypes: stats?.prototypes ?? 0 } }

  return reactive({
    iterations, selectedIterationId, iterationStats,
    iterationDialogVisible: formManager.iterationDialogVisible,
    iterationDialogMode: formManager.iterationDialogMode,
    iterationFormRef: formManager.iterationFormRef,
    iterationFormData: formManager.iterationFormData,
    iterationFormRules: formManager.iterationFormRules,
    submitting: formManager.submitting,
    safeIterations, validIterationsForSelect,
    get isSubmitting() { return formManager.submitting.value === true },
    loadIterations, handleSelectIteration, getIterationIdParam,
    handleAddIteration: formManager.handleAddIteration,
    handleEditIteration: formManager.handleEditIteration,
    handleDeleteIteration, handleIterationCommand,
    handleIterationSubmit: formManager.handleIterationSubmit,
    resetIterationForm: formManager.resetIterationForm,
    getIterationStatusType, getIterationStatusText, getCurrentIterationTitle,
    getIterationNameById, getIterationStatsById, showError: formManager.showError,
  })
}
