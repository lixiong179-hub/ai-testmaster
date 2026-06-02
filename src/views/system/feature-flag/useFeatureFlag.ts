import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { featureFlagApi } from '@/api/featureFlag'
import type { FeatureFlagItem, FeatureFlagCreate, FeatureFlagUpdate } from '@/api/featureFlag'
import { ProjectAPI } from '@/api/project'
import type { Project } from '@/api/project'

/** FeatureFlag 表单数据 */
interface FlagFormData {
  key: string
  name: string
  description: string
  enabled: boolean
  rollout_percentage: number
  target_type: 'all' | 'specific'
  target_project_ids: number[]
}

/** 目标类型选项 */
const TARGET_TYPE_OPTIONS = [
  { label: '全部项目', value: 'all' as const },
  { label: '指定项目', value: 'specific' as const },
] as const

export function useFeatureFlag() {
  const loading = ref(false)
  const flags = ref<FeatureFlagItem[]>([])
  const projects = ref<Project[]>([])

  // 对话框状态
  const dialogVisible = ref(false)
  const dialogTitle = ref('新增 FeatureFlag')
  const editMode = ref(false)
  const currentFlagKey = ref<string | null>(null)
  const formRef = ref()

  // 表单数据
  const formData = reactive<FlagFormData>({
    key: '',
    name: '',
    description: '',
    enabled: false,
    rollout_percentage: 0,
    target_type: 'all',
    target_project_ids: [],
  })

  // 表单校验规则
  const formRules = {
    key: [
      { required: true, message: '请输入Flag Key', trigger: 'blur' },
      { min: 1, max: 100, message: 'Key长度1-100位', trigger: 'blur' },
    ],
    name: [
      { required: true, message: '请输入Flag名称', trigger: 'blur' },
      { min: 1, max: 200, message: '名称长度1-200位', trigger: 'blur' },
    ],
    target_type: [{ required: true, message: '请选择目标类型', trigger: 'change' }],
  }

  /** 加载项目列表（用于目标项目多选） */
  const loadProjects = async (): Promise<void> => {
    try {
      const response = await ProjectAPI.getProjects({ page: 1, page_size: 100 })
      projects.value = response.data?.items ?? []
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '获取项目列表失败'
      ElMessage.error(msg)
    }
  }

  /** 加载 FeatureFlag 列表 */
  const loadFlags = async (): Promise<void> => {
    loading.value = true
    try {
      const response = await featureFlagApi.getFeatureFlags()
      flags.value = Array.isArray(response.data) ? response.data : []
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '获取FeatureFlag列表失败'
      ElMessage.error(msg)
    } finally {
      loading.value = false
    }
  }

  /** 切换 FeatureFlag 启用状态 */
  const handleToggle = async (row: FeatureFlagItem): Promise<void> => {
    try {
      await featureFlagApi.toggleFeatureFlag(row.key, row.enabled)
      ElMessage.success(row.enabled ? '已启用' : '已禁用')
    } catch (error: unknown) {
      // 回滚开关状态
      row.enabled = !row.enabled
      const msg = error instanceof Error ? error.message : '切换状态失败'
      ElMessage.error(msg)
    }
  }

  /** 重置表单 */
  const resetForm = (): void => {
    Object.assign(formData, {
      key: '',
      name: '',
      description: '',
      enabled: false,
      rollout_percentage: 0,
      target_type: 'all',
      target_project_ids: [],
    })
    currentFlagKey.value = null
  }

  /** 打开新增对话框 */
  const openAddDialog = (): void => {
    editMode.value = false
    dialogTitle.value = '新增 FeatureFlag'
    resetForm()
    dialogVisible.value = true
  }

  /** 打开编辑对话框 */
  const openEditDialog = (row: FeatureFlagItem): void => {
    editMode.value = true
    dialogTitle.value = '编辑 FeatureFlag'
    currentFlagKey.value = row.key
    Object.assign(formData, {
      key: row.key,
      name: row.name,
      description: row.description ?? '',
      enabled: row.enabled,
      rollout_percentage: row.rollout_percentage,
      target_type: row.target_type,
      target_project_ids: [...row.target_project_ids],
    })
    dialogVisible.value = true
  }

  /** 保存 FeatureFlag */
  const saveFlag = async (): Promise<void> => {
    if (!formRef.value) return
    await formRef.value.validate(async (valid: boolean) => {
      if (!valid) return
      try {
        if (editMode.value && currentFlagKey.value !== null) {
          const updateData: FeatureFlagUpdate = {
            name: formData.name,
            description: formData.description || undefined,
            enabled: formData.enabled,
            rollout_percentage: formData.rollout_percentage,
            target_type: formData.target_type,
            target_project_ids:
              formData.target_type === 'specific' ? formData.target_project_ids : [],
          }
          await featureFlagApi.updateFeatureFlag(currentFlagKey.value, updateData)
          ElMessage.success('FeatureFlag 更新成功')
        } else {
          const createData: FeatureFlagCreate = {
            key: formData.key,
            name: formData.name,
            description: formData.description || undefined,
            enabled: formData.enabled,
            rollout_percentage: formData.rollout_percentage,
            target_type: formData.target_type,
            target_project_ids:
              formData.target_type === 'specific' ? formData.target_project_ids : [],
          }
          await featureFlagApi.createFeatureFlag(createData)
          ElMessage.success('FeatureFlag 创建成功')
        }
        dialogVisible.value = false
        await loadFlags()
      } catch (error: unknown) {
        const msg = error instanceof Error ? error.message : '保存失败'
        ElMessage.error(msg)
      }
    })
  }

  /** 删除 FeatureFlag */
  const deleteFlag = (row: FeatureFlagItem): void => {
    ElMessageBox.confirm(
      `确定要删除 FeatureFlag「${row.name}」吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
      .then(async () => {
        try {
          await featureFlagApi.deleteFeatureFlag(row.key)
          ElMessage.success('删除成功')
          await loadFlags()
        } catch (error: unknown) {
          const msg = error instanceof Error ? error.message : '删除失败'
          ElMessage.error(msg)
        }
      })
      .catch(() => {
        /* 用户取消 */
      })
  }

  /** 获取目标项目名称列表 */
  const getProjectNames = (projectIds: number[]): string => {
    if (!projectIds || projectIds.length === 0) return '-'
    const names = projectIds
      .map((id) => projects.value.find((p) => p.id === id)?.name)
      .filter((name): name is string => name !== undefined)
    return names.length > 0 ? names.join('、') : '-'
  }

  onMounted(() => {
    loadProjects()
    loadFlags()
  })

  return {
    loading,
    flags,
    projects,
    dialogVisible,
    dialogTitle,
    editMode,
    formRef,
    formData,
    formRules,
    TARGET_TYPE_OPTIONS,
    handleToggle,
    openAddDialog,
    openEditDialog,
    saveFlag,
    deleteFlag,
    getProjectNames,
  }
}
