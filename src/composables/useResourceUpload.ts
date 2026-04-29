/**
 * 资源上传 Composable
 * 职责：上传表单、文件选择、提交逻辑
 */
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, UploadFile as ElUploadFile } from 'element-plus'
import { uiPrototypeApi } from '@/api/uiPrototype'
import request from '@/utils/request'
import { RESOURCE_CONFIG } from '@/constants/resource'
import type { Resource } from './useResourceList'

interface ResourceFormData {
  id: number | null;
  project_id: number | '';
  name: string;
  resource_type: string;
  file: File | null;
  description: string;
  is_active: boolean;
  iteration_id: number | null;
}

interface ApiResponseData {
  code?: number;
  data?: unknown;
  total?: number;
}

export function useResourceUpload(
  iterationManager: ReturnType<typeof import('./useIterationManager').useIterationManager>,
  refreshResources: () => void
) {
  // 状态定义
  const fileDialogVisible = ref(false)
  const fileDialogMode = ref<'add' | 'edit'>('add')
  const fileFormRef = ref<FormInstance>()
  const uploadRef = ref<InstanceType<typeof import('element-plus')['ElUpload']>>()
  const submitting = ref(false)

  // ✅ 强制确保弹窗初始化时关闭（解决自动打开的问题）
  fileDialogVisible.value = false

  // 安全的loading状态（确保模板中拿到的是boolean而非ref对象）
  const selectedFile = ref<File | null>(null)
  const selectedFiles = ref<File[]>([])

  // 文件表单数据
  const fileFormData = reactive<ResourceFormData>({
    id: null,
    project_id: '' as number | '',
    name: '',
    resource_type: 'requirement',
    file: null,
    description: '',
    is_active: true,
    iteration_id: null
  })

  // 表单验证规则
  const fileFormRules = {
    project_id: [{ required: true, message: '请选择项目', trigger: 'change' }],
    name: [{ required: true, message: '请输入资源名称', trigger: 'blur' }],
    resource_type: [{ required: true, message: '请选择资源类型', trigger: 'change' }]
  }

  // 计算属性：弹窗标题
  const fileDialogTitle = computed(() => fileDialogMode.value === 'add' ? '上传文件' : '编辑文件')

  // 内部辅助：是否为批量上传模式
  const checkIsBatchUpload = (): boolean => fileFormData.resource_type === 'ui_mockup' && fileDialogMode.value === 'add'

  /**
   * 打开新增文件弹窗
   */
  const handleAddFile = () => {
    if (!iterationManager.iterations || iterationManager.selectedIterationId === undefined) {
      return
    }
    resetFileForm()
    fileDialogMode.value = 'add'

    if (iterationManager.selectedIterationId !== null && iterationManager.selectedIterationId > 0) {
      fileFormData.iteration_id = iterationManager.selectedIterationId
    } else if (iterationManager.selectedIterationId === 0) {
      fileFormData.iteration_id = RESOURCE_CONFIG.ITERATION_UNCLASSIFIED
    } else {
      fileFormData.iteration_id = null
    }

    fileDialogVisible.value = true
  }

  /**
   * 打开编辑文件弹窗
   * @param row 资源行数据
   */
  const handleEdit = (row: Resource) => {
    fileFormData.id = row.id
    fileFormData.project_id = row.project_id
    fileFormData.name = row.name
    fileFormData.resource_type = row.resource_type
    fileFormData.description = row.description || ''
    fileFormData.is_active = row.is_active

    // 设置当前迭代值（用于编辑弹窗中的迭代选择器）
    if (row.iteration_id != null && row.iteration_id !== 0) {
      fileFormData.iteration_id = row.iteration_id
    } else {
      fileFormData.iteration_id = RESOURCE_CONFIG.ITERATION_UNCLASSIFIED
    }

    fileDialogMode.value = 'edit'
    fileDialogVisible.value = true
  }

  /**
   * 重置文件表单
   */
  const resetFileForm = () => {
    fileFormData.id = null
    fileFormData.project_id = ''
    fileFormData.name = ''
    fileFormData.resource_type = 'requirement'
    fileFormData.file = null
    fileFormData.description = ''
    fileFormData.is_active = true
    fileFormData.iteration_id = null  // 重置为null，避免ElOption收到undefined
    selectedFile.value = null
    selectedFiles.value = []
  }

  /**
   * 文件选择变化处理
   */
  const handleFileChange = (file: ElUploadFile, fileList: ElUploadFile[]) => {
    if (checkIsBatchUpload()) {
      selectedFiles.value = fileList.map((f: ElUploadFile) => f.raw as File)
      if (!fileFormData.name && fileList.length > 0) {
        fileFormData.name = 'UI原型图批量上传'
      }
    } else {
      selectedFile.value = file.raw as File
      fileFormData.file = file.raw as File
      if (!fileFormData.name) {
        fileFormData.name = file.name.replace(/\.[^.]+$/, '')
      }
    }
  }

  /**
   * 文件移除处理
   */
  const handleFileRemove = (_file: ElUploadFile, fileList: ElUploadFile[]) => {
    if (checkIsBatchUpload()) {
      selectedFiles.value = fileList.map((f: ElUploadFile) => f.raw as File)
    } else {
      selectedFile.value = null
      fileFormData.file = null
    }
  }

  /**
   * 文件数量超限处理
   */
  const handleExceed = () => {
    ElMessage.warning(checkIsBatchUpload() ? '最多上传20个文件' : '只能上传1个文件')
  }

  /**
   * 获取当前选中迭代的名称
   */
  const getCurrentIterationName = (): string => {
    if (fileFormData.iteration_id === null || fileFormData.iteration_id === undefined) return '未选择'
    if (fileFormData.iteration_id === RESOURCE_CONFIG.ITERATION_UNCLASSIFIED) return '未分类'
    return iterationManager.getIterationNameById(fileFormData.iteration_id)
  }

  /**
   * 提交文件表单（上传或编辑）
   * @param externalFormRef 可选的外部表单 ref，如果提供则使用它进行验证
   */
  const handleFileSubmit = async (externalFormRef?: FormInstance) => {
    const formRefToUse = externalFormRef || fileFormRef.value

    if (!formRefToUse) {
      ElMessage.error('表单初始化失败，请刷新页面重试')
      return
    }

    try {
      await formRefToUse.validate()
    } catch {
      return
    }

    submitting.value = true
    try {
      // 编辑模式
      if (fileDialogMode.value === 'edit' && fileFormData.id) {
        const response = await request.put(`/api/v1/file/${fileFormData.id}`, {
          resource_type: fileFormData.resource_type,
          description: fileFormData.description,
          iteration_id: fileFormData.iteration_id
        })
        if ((response as ApiResponseData)?.code === 200) {
          ElMessage.success('文件信息更新成功')
        }
        fileDialogVisible.value = false
        refreshResources()
        return
      }

      // 批量上传UI原型图
      if (checkIsBatchUpload()) {
        if (!selectedFiles.value || selectedFiles.value.length === 0) {
          ElMessage.warning('请选择文件')
          return
        }

        const response = await uiPrototypeApi.uploadUIScreens(
          fileFormData.project_id as number,
          selectedFiles.value,
          fileFormData.name || 'UI原型图',
          undefined,
          // ✅ 修复：使用统一的iteration_id转换逻辑
          fileFormData.iteration_id !== null
            ? (fileFormData.iteration_id === RESOURCE_CONFIG.ITERATION_UNCLASSIFIED ? -1 : fileFormData.iteration_id)
            : undefined
        )

        const result = response?.data || response
        if (result?.total > 0) {
          ElMessage.success(`成功上传 ${result.total} 张UI原型图到迭代 "${getCurrentIterationName()}"`)
        } else {
          ElMessage.warning('上传完成，但未成功创建任何屏幕记录')
        }

        fileDialogVisible.value = false
        refreshResources()
        return
      }

      // 单文件上传
      if (!selectedFile.value && fileDialogMode.value === 'add') {
        ElMessage.warning('请选择文件')
        return
      }

      const formData = new FormData()
      formData.append('file', selectedFile.value as File)
      formData.append('project_id', fileFormData.project_id.toString())
      formData.append('resource_type', fileFormData.resource_type)
      formData.append('description', fileFormData.description || '')
      // ✅ 修复：使用统一的iteration_id转换逻辑
      if (fileFormData.iteration_id !== null) {
        const iterationValue = fileFormData.iteration_id === RESOURCE_CONFIG.ITERATION_UNCLASSIFIED ? -1 : fileFormData.iteration_id
        formData.append('iteration_id', iterationValue.toString())
      }

      const response = await request.post('/api/v1/file/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })

      if ((response as ApiResponseData)?.code === 200 || response?.data) {
        ElMessage.success(`文件 "${fileFormData.name}" 上传成功`)
      }

      fileDialogVisible.value = false
      refreshResources()
    } catch (error: unknown) {
      iterationManager.showError('上传文件', error)
    } finally {
      submitting.value = false
    }
  }

  return reactive({
    fileDialogVisible,
    fileDialogMode,
    fileFormRef,
    uploadRef,
    submitting,
    get isSubmitting() { return submitting.value === true },
    selectedFile,
    selectedFiles,
    fileFormData,
    fileFormRules,
    fileDialogTitle,
    get isBatchUpload() { return fileFormData.resource_type === 'ui_mockup' && fileDialogMode.value === 'add' },

    handleAddFile,
    handleEdit,
    resetFileForm,
    handleFileChange,
    handleFileRemove,
    handleExceed,
    handleFileSubmit,
    getCurrentIterationName
  })
}
