import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { testCapabilityApi } from '@/api/testCapability'
import type {
  TestCapabilityResponse,
  TestCapabilityCreateRequest,
  TestCapabilityUpdateRequest,
} from '@/api/testCapability'
import { ProjectAPI } from '@/api/project'
import type { Project } from '@/api/project'

/** 测试能力表单数据 */
interface CapabilityFormData {
  key: string
  title: string
  description: string
  status: string
}

/** 状态选项 */
const STATUS_OPTIONS = [
  { label: '活跃', value: 'active' },
  { label: '停用', value: 'inactive' },
  { label: '废弃', value: 'deprecated' },
] as const

/** 状态标签类型映射 */
const STATUS_TAG_TYPE: Record<string, 'success' | 'info' | 'warning'> = {
  active: 'success',
  inactive: 'info',
  deprecated: 'warning',
}

export function useTestCapability() {
  const loading = ref(false)
  const capabilities = ref<TestCapabilityResponse[]>([])
  const projects = ref<Project[]>([])

  // 当前选中的项目ID
  const selectedProjectId = ref<number | null>(null)

  // 对话框状态
  const dialogVisible = ref(false)
  const dialogTitle = ref('新增测试能力')
  const editMode = ref(false)
  const currentCapabilityId = ref<number | null>(null)
  const formRef = ref()

  // 表单数据
  const formData = reactive<CapabilityFormData>({
    key: '',
    title: '',
    description: '',
    status: 'active',
  })

  // 表单校验规则
  const formRules = {
    key: [
      { required: true, message: '请输入能力Key', trigger: 'blur' },
      { min: 1, max: 100, message: 'Key长度1-100位', trigger: 'blur' },
    ],
    title: [
      { required: true, message: '请输入能力标题', trigger: 'blur' },
      { min: 1, max: 200, message: '标题长度1-200位', trigger: 'blur' },
    ],
    status: [{ required: true, message: '请选择状态', trigger: 'change' }],
  }

  /** 加载项目列表 */
  const loadProjects = async (): Promise<void> => {
    try {
      const response = await ProjectAPI.getProjects({ page: 1, page_size: 100 })
      projects.value = response.data?.items ?? []
      // 自动选中第一个项目
      if (projects.value.length > 0 && !selectedProjectId.value) {
        selectedProjectId.value = projects.value[0].id
        await loadCapabilities()
      }
    } catch (error) {
      ElMessage.error('获取项目列表失败')
    }
  }

  /** 加载测试能力列表 */
  const loadCapabilities = async (): Promise<void> => {
    if (!selectedProjectId.value) {
      capabilities.value = []
      return
    }
    loading.value = true
    try {
      const response = await testCapabilityApi.getList({
        project_id: selectedProjectId.value,
      })
      capabilities.value = Array.isArray(response.data) ? response.data : []
    } catch (error) {
      ElMessage.error('获取测试能力列表失败')
    } finally {
      loading.value = false
    }
  }

  /** 项目切换 */
  const handleProjectChange = (): void => {
    loadCapabilities()
  }

  /** 获取状态标签类型 */
  const getStatusTagType = (status: string): 'success' | 'info' | 'warning' => {
    return STATUS_TAG_TYPE[status] ?? 'info'
  }

  /** 获取状态标签文本 */
  const getStatusLabel = (status: string): string => {
    const option = STATUS_OPTIONS.find((o) => o.value === status)
    return option?.label ?? status
  }

  /** 重置表单 */
  const resetForm = (): void => {
    Object.assign(formData, {
      key: '',
      title: '',
      description: '',
      status: 'active',
    })
    currentCapabilityId.value = null
  }

  /** 打开新增对话框 */
  const openAddDialog = (): void => {
    if (!selectedProjectId.value) {
      ElMessage.warning('请先选择项目')
      return
    }
    editMode.value = false
    dialogTitle.value = '新增测试能力'
    resetForm()
    dialogVisible.value = true
  }

  /** 打开编辑对话框 */
  const openEditDialog = (row: TestCapabilityResponse): void => {
    editMode.value = true
    dialogTitle.value = '编辑测试能力'
    currentCapabilityId.value = row.id
    Object.assign(formData, {
      key: row.key,
      title: row.title,
      description: row.description ?? '',
      status: row.status,
    })
    dialogVisible.value = true
  }

  /** 保存测试能力 */
  const saveCapability = async (): Promise<void> => {
    if (!formRef.value) return
    await formRef.value.validate(async (valid: boolean) => {
      if (!valid) return
      try {
        if (editMode.value && currentCapabilityId.value !== null) {
          const updateData: TestCapabilityUpdateRequest = {
            key: formData.key,
            title: formData.title,
            description: formData.description || undefined,
            status: formData.status,
          }
          await testCapabilityApi.update(currentCapabilityId.value, updateData)
          ElMessage.success('测试能力更新成功')
        } else {
          const createData: TestCapabilityCreateRequest = {
            project_id: selectedProjectId.value!,
            key: formData.key,
            title: formData.title,
            description: formData.description || undefined,
            status: formData.status,
          }
          await testCapabilityApi.create(createData)
          ElMessage.success('测试能力创建成功')
        }
        dialogVisible.value = false
        await loadCapabilities()
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : '保存失败'
        ElMessage.error(message)
      }
    })
  }

  /** 删除测试能力 */
  const deleteCapability = (row: TestCapabilityResponse): void => {
    ElMessageBox.confirm(`确定要删除测试能力「${row.title}」吗？`, '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
      .then(async () => {
        try {
          await testCapabilityApi.delete(row.id)
          ElMessage.success('删除成功')
          await loadCapabilities()
        } catch (error) {
          ElMessage.error('删除失败')
        }
      })
      .catch(() => {
        /* 用户取消 */
      })
  }

  onMounted(() => {
    loadProjects()
  })

  return {
    // 状态
    loading,
    capabilities,
    projects,
    selectedProjectId,
    dialogVisible,
    dialogTitle,
    editMode,
    formRef,
    formData,
    formRules,
    STATUS_OPTIONS,
    // 方法
    handleProjectChange,
    getStatusTagType,
    getStatusLabel,
    openAddDialog,
    openEditDialog,
    saveCapability,
    deleteCapability,
  }
}
