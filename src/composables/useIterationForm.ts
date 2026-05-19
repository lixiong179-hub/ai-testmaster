import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { iterationApi, type Iteration, type IterationUpdateRequest } from '@/api/iteration'

export function useIterationForm() {
  const iterationDialogVisible = ref(false)
  const iterationDialogMode = ref<'add' | 'edit'>('add')
  const iterationFormRef = ref<FormInstance>()
  const submitting = ref(false)

  iterationDialogVisible.value = false

  const iterationFormData = reactive({
    id: null as number | null,
    project_id: null as number | null,
    name: '',
    version: 'v1.0',
    description: '',
    status: 'planning' as string,
    start_date: '',
    end_date: '',
  })

  const iterationFormRules = {
    name: [{ required: true, message: '请输入代表迭名称', trigger: 'blur' }],
    version: [{ required: true, message: '请输入版本号', trigger: 'blur' }],
    status: [{ required: true, message: '请选择状态', trigger: 'change' }],
  }

  const resetIterationForm = () => {
    iterationFormData.id = null
    iterationFormData.project_id = null
    iterationFormData.name = ''
    iterationFormData.version = 'v1.0'
    iterationFormData.description = ''
    iterationFormData.status = 'planning'
    iterationFormData.start_date = ''
    iterationFormData.end_date = ''
  }

  const handleAddIteration = (projectId: number) => {
    if (!projectId) { ElMessage.warning('请先选择项目'); return }
    resetIterationForm()
    iterationDialogMode.value = 'add'
    iterationFormData.project_id = projectId
    iterationDialogVisible.value = true
  }

  const handleEditIteration = (iteration: Iteration) => {
    resetIterationForm()
    iterationDialogMode.value = 'edit'
    iterationFormData.id = iteration.id
    iterationFormData.project_id = iteration.project_id
    iterationFormData.name = iteration.name
    iterationFormData.version = iteration.version
    iterationFormData.description = iteration.description || ''
    iterationFormData.status = iteration.status
    iterationFormData.start_date = iteration.start_date ? iteration.start_date.substring(0, 10) : ''
    iterationFormData.end_date = iteration.end_date ? iteration.end_date.substring(0, 10) : ''
    iterationDialogVisible.value = true
  }

  const showError = (operation: string, error: unknown) => {
    console.error(`[${operation}] 操作失败详情:`, error)
    let userMsg = `${operation}失败`
    const errorObj = error as { response?: { data?: { detail?: string } } }
    const detail = errorObj?.response?.data?.detail
    if (typeof detail === 'string') {
      if (detail.includes('UniqueConstraint') || detail.includes('已存在')) userMsg = `${operation}失败：数据已存在，请检查是否重复`
      else if (detail.includes('403') || detail.includes('权限')) userMsg = `${operation}失败：您没有权限执行此操作`
      else if (detail.includes('404') || detail.includes('不存在')) userMsg = `${operation}失败：请求的资源不存在`
      else userMsg = `${operation}失败，请稍后重试或联系管理员`
    }
    ElMessage.error(userMsg)
  }

  const handleIterationSubmit = async (externalFormRef?: FormInstance): Promise<boolean> => {
    const formRefToUse = externalFormRef || iterationFormRef.value
    if (!formRefToUse) { ElMessage.error('表单初始化失败，请刷新页面重试'); return false }
    if (!externalFormRef) { try { await formRefToUse.validate() } catch { return false } }
    submitting.value = true
    try {
      if (iterationDialogMode.value === 'edit' && iterationFormData.id) {
        const updateData: IterationUpdateRequest = {
          name: iterationFormData.name, version: iterationFormData.version,
          description: iterationFormData.description || undefined, status: iterationFormData.status,
          start_date: iterationFormData.start_date || undefined, end_date: iterationFormData.end_date || undefined,
        }
        await iterationApi.updateIteration(iterationFormData.id, updateData)
        ElMessage.success(`迭代 "${iterationFormData.name}" 更新成功`)
      } else {
        if (!iterationFormData.project_id) { ElMessage.error('项目ID缺失，请刷新页面重试'); return false }
        const createData = {
          project_id: iterationFormData.project_id, name: iterationFormData.name,
          version: iterationFormData.version, description: iterationFormData.description || undefined,
          status: iterationFormData.status, start_date: iterationFormData.start_date || undefined,
          end_date: iterationFormData.end_date || undefined,
        }
        await iterationApi.createIteration(createData)
        ElMessage.success(`迭代 "${iterationFormData.name}" 创建成功`)
      }
      iterationDialogVisible.value = false
      return true
    } catch (error: unknown) {
      showError(iterationDialogMode.value === 'edit' ? '更新迭代' : '创建迭代', error)
      return false
    } finally { submitting.value = false }
  }

  return {
    iterationDialogVisible, iterationDialogMode, iterationFormRef, submitting,
    iterationFormData, iterationFormRules,
    handleAddIteration, handleEditIteration, handleIterationSubmit, resetIterationForm, showError,
  }
}
