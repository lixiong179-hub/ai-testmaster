/**
 * 迭代管理 Composable
 * 职责：迭代的CRUD、选择状态管理、统计信息
 */
import { ref, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { iterationApi, type Iteration, type IterationUpdateRequest } from '@/api/iteration'
import { fileApi } from '@/api/file'
import { uiPrototypeApi } from '@/api/uiPrototype'

/**
 * 迭代筛选状态的联合类型
 * - null: 显示项目下所有资源（"全部"）
 * - 0: 仅显示未分类的资源（iteration_id 为 NULL）
 * - 具体数字 (>0): 显示特定迭代下的资源
 */
export type IterationSelection = null | 0 | number

/**
 * 安全的迭代类型（经过 safeIterations 计算属性处理后的类型）
 */
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
  // 状态定义
  const iterations = ref<Iteration[]>([])
  const selectedIterationId = ref<IterationSelection>(null)
  const iterationStats = ref<Record<number, { files: number; prototypes: number }>>({})

  // 安全的迭代列表计算属性（100%确保返回有效数组，没有undefined/null元素）
  const safeIterations = computed<SafeIteration[]>(() => {
    try {
      const arr = Array.isArray(iterations.value) ? iterations.value : []
      const validArr = arr
        .filter(
          (it: Iteration) =>
            it && typeof it === 'object' && it.id != null && Number.isInteger(it.id)
        )
        .map((it: Iteration) => ({
          id: it.id,
          project_id: it.project_id,
          name: it.name || '未命名迭代',
          version: it.version || 'v1.0',
          description: it.description || '',
          status: it.status || 'planning',
          start_date: it.start_date || null,
          end_date: it.end_date || null,
          create_time: it.create_time || new Date().toISOString(),
          update_time: it.update_time || new Date().toISOString(),
        }))
      return validArr
    } catch {
      return []
    }
  })

  // 用于下拉选择的有效迭代列表（过滤掉无效id的）
  const validIterationsForSelect = computed<SafeIteration[]>(() => {
    return safeIterations.value.filter((it) => it.id)
  })

  // 迭代弹窗相关状态
  const iterationDialogVisible = ref(false)
  const iterationDialogMode = ref<'add' | 'edit'>('add')
  const iterationFormRef = ref<FormInstance>()
  const submitting = ref(false)

  // ✅ 强制确保弹窗初始化时关闭（解决自动打开的问题）
  iterationDialogVisible.value = false

  // 迭代表单数据
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

  // 表单验证规则
  const iterationFormRules = {
    name: [{ required: true, message: '请输入代表迭名称', trigger: 'blur' }],
    version: [{ required: true, message: '请输入版本号', trigger: 'blur' }],
    status: [{ required: true, message: '请选择状态', trigger: 'change' }],
  }

  /**
   * 从响应数据中提取列表项
   */
  function extractListItems(res: unknown): Record<string, unknown>[] {
    if (!res || typeof res !== 'object') return []
    if (Array.isArray(res)) return res as Record<string, unknown>[]
    const resObj = res as Record<string, unknown>
    if (Array.isArray(resObj.items)) return resObj.items as Record<string, unknown>[]
    const d = resObj.data
    if (d && typeof d === 'object' && Array.isArray((d as Record<string, unknown>).items))
      return (d as Record<string, unknown>).items as Record<string, unknown>[]
    return []
  }

  /**
   * 加载指定项目下的迭代列表及统计信息
   */
  const loadIterations = async (projectId: number) => {
    if (!projectId) {
      iterations.value = []
      iterationStats.value = {}
      return
    }
    try {
      const response = await iterationApi.getIterations(projectId)
      const items = extractListItems(response)
      iterations.value = items as unknown as Iteration[]

      await Promise.all(
        (items as unknown as Iteration[]).map(async (it: Iteration) => {
          try {
            const [fileRes, protoRes] = await Promise.all([
              fileApi.getFileList(projectId, it.id, 1, 1),
              uiPrototypeApi.getUIPrototypeProjectList(projectId, 1, 1, it.id),
            ])

            const fileData = fileRes as unknown as Record<string, unknown>
            const fileResponseData = fileData?.data as Record<string, unknown> | undefined
            const fileTotal =
              (fileResponseData?.total as number) ||
              (extractListItems(fileRes).length > 0 ? (fileResponseData?.total as number) || 0 : 0)

            const protoData = protoRes as unknown as Record<string, unknown>
            const protoResponseData = protoData?.data as Record<string, unknown> | undefined
            const protoTotal =
              (protoResponseData?.total as number) ||
              (extractListItems(protoRes).length > 0
                ? (protoResponseData?.total as number) || 0
                : 0)

            iterationStats.value[it.id] = {
              files: fileTotal,
              prototypes: protoTotal,
            }
          } catch (e) {
            console.warn(`获取迭代 ${it.name} 统计失败:`, e)
            iterationStats.value[it.id] = { files: 0, prototypes: 0 }
          }
        })
      )
    } catch (error) {
      console.error('获取迭代列表失败:', error)
      iterations.value = []
      iterationStats.value = {}
    }
  }

  /**
   * 选择迭代进行筛选
   */
  const handleSelectIteration = (iterationId: IterationSelection) => {
    selectedIterationId.value = iterationId
  }

  /**
   * 将前端迭代筛选状态转换为后端API参数
   * - null → undefined（不传参数，后端返回全部）
   * - 0 → -1（后端约定：-1 表示筛选"未分类"资源）
   * - 具体数字 → 直接返回该迭代ID
   */
  const getIterationIdParam = (): number | undefined => {
    if (selectedIterationId.value === null) {
      return undefined // 不传参数，后端返回全部
    }
    if (selectedIterationId.value === 0) {
      return -1 // 后端约定：-1 表示筛选"未分类"
    }
    return selectedIterationId.value // 返回具体的迭代ID
  }

  /**
   * 打开新建迭代弹窗
   */
  const handleAddIteration = (projectId: number) => {
    if (!projectId) {
      ElMessage.warning('请先选择项目')
      return
    }
    resetIterationForm()
    iterationDialogMode.value = 'add'
    iterationFormData.project_id = projectId
    iterationDialogVisible.value = true
  }

  /**
   * 打开编辑迭代弹窗
   */
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

  /**
   * 删除迭代
   */
  const handleDeleteIteration = async (iteration: Iteration) => {
    try {
      await ElMessageBox.confirm(
        '删除迭代将同时删除其下所有需求文档和UI原型图，确定要删除吗？',
        '删除确认',
        { type: 'warning' }
      )
      await iterationApi.deleteIteration(iteration.id)
      ElMessage.success(`迭代 "${iteration.name}" 及其下的所有资源已删除`)
      if (selectedIterationId.value === iteration.id) {
        selectedIterationId.value = null
      }
      // 需要从外部调用 loadIterations 和 getResources
      return true // 表示需要刷新
    } catch (error: unknown) {
      if (error !== 'cancel') {
        showError('删除迭代', error)
      }
      return false
    }
  }

  /**
   * 处理迭代操作命令（编辑/删除）
   */
  const handleIterationCommand = async (
    command: string,
    iteration: Iteration
  ): Promise<boolean> => {
    if (command === 'edit') {
      handleEditIteration(iteration)
      return false // 不需要刷新
    } else if (command === 'delete') {
      return await handleDeleteIteration(iteration) // 返回是否需要刷新
    }
    return false
  }

  /**
   * 提交迭代表单（创建或更新）
   * @param externalFormRef 可选的外部表单 ref，如果提供则使用它进行验证
   */
  const handleIterationSubmit = async (externalFormRef?: FormInstance): Promise<boolean> => {
    const formRefToUse = externalFormRef || iterationFormRef.value

    if (!formRefToUse) {
      ElMessage.error('表单初始化失败，请刷新页面重试')
      return false
    }

    if (!externalFormRef) {
      try {
        await formRefToUse.validate()
      } catch {
        return false
      }
    }

    submitting.value = true
    try {
      if (iterationDialogMode.value === 'edit' && iterationFormData.id) {
        const updateData: IterationUpdateRequest = {
          name: iterationFormData.name,
          version: iterationFormData.version,
          description: iterationFormData.description || undefined,
          status: iterationFormData.status,
          start_date: iterationFormData.start_date || undefined,
          end_date: iterationFormData.end_date || undefined,
        }
        await iterationApi.updateIteration(iterationFormData.id, updateData)
        ElMessage.success(`迭代 "${iterationFormData.name}" 更新成功`)
      } else {
        if (!iterationFormData.project_id) {
          ElMessage.error('项目ID缺失，请刷新页面重试')
          return false
        }
        const createData = {
          project_id: iterationFormData.project_id,
          name: iterationFormData.name,
          version: iterationFormData.version,
          description: iterationFormData.description || undefined,
          status: iterationFormData.status,
          start_date: iterationFormData.start_date || undefined,
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
    } finally {
      submitting.value = false
    }
  }

  /**
   * 重置迭代表单
   */
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

  /**
   * 获取迭代状态标签类型
   */
  const getIterationStatusType = (status: string): string => {
    const typeMap: Record<string, string> = {
      planning: 'info',
      active: 'success',
      completed: '',
      archived: 'warning',
    }
    return typeMap[status] || 'info'
  }

  /**
   * 获取迭代状态文本
   */
  const getIterationStatusText = (status: string): string => {
    const textMap: Record<string, string> = {
      planning: '规划中',
      active: '进行中',
      completed: '已完成',
      archived: '已归档',
    }
    return textMap[status] || status
  }

  /**
   * 根据当前选中的迭代状态计算标题文本
   */
  const getCurrentIterationTitle = (): string => {
    if (selectedIterationId.value === null) return '全部资源'
    if (selectedIterationId.value === 0) return '未分类资源'
    // 查找具体迭代的名称和版本
    const iteration = iterations.value.find((it) => it.id === selectedIterationId.value)
    return iteration ? `${iteration.name} (${iteration.version})` : '资源列表'
  }

  /**
   * 获取指定迭代ID的名称
   */
  const getIterationNameById = (id: number): string => {
    if (id === 0) return '未分类'
    const it = iterations.value.find((i) => i.id === id)
    return it ? it.name : '未知迭代'
  }

  /**
   * 错误处理方法（带脱敏）
   */
  const showError = (operation: string, error: unknown) => {
    console.error(`[${operation}] 操作失败详情:`, error)

    let userMsg = `${operation}失败`

    const errorObj = error as { response?: { data?: { detail?: string } } }
    const detail = errorObj?.response?.data?.detail

    // 根据错误类型生成友好的用户提示
    if (typeof detail === 'string') {
      if (detail.includes('UniqueConstraint') || detail.includes('已存在')) {
        userMsg = `${operation}失败：数据已存在，请检查是否重复`
      } else if (detail.includes('403') || detail.includes('权限')) {
        userMsg = `${operation}失败：您没有权限执行此操作`
      } else if (detail.includes('404') || detail.includes('不存在')) {
        userMsg = `${operation}失败：请求的资源不存在`
      } else {
        // 默认只显示通用提示，不暴露细节
        userMsg = `${operation}失败，请稍后重试或联系管理员`
      }
    }

    ElMessage.error(userMsg)
  }

  return reactive({
    iterations,
    selectedIterationId,
    iterationStats,
    iterationDialogVisible,
    iterationDialogMode,
    iterationFormRef,
    iterationFormData,
    iterationFormRules,
    submitting,

    safeIterations,
    validIterationsForSelect,
    get isSubmitting() {
      return submitting.value === true
    },

    loadIterations,
    handleSelectIteration,
    getIterationIdParam,
    handleAddIteration,
    handleEditIteration,
    handleDeleteIteration,
    handleIterationCommand,
    handleIterationSubmit,
    resetIterationForm,
    getIterationStatusType,
    getIterationStatusText,
    getCurrentIterationTitle,
    getIterationNameById,
    showError,
  })
}
