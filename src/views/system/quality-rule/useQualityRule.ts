import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { qualityRuleApi } from '@/api/qualityRule'
import type { QualityRuleItem } from '@/api/qualityRule'
import { ProjectAPI } from '@/api/project'
import type { Project } from '@/api/project'

/** 规则编辑表单数据 - 使用联合类型字段 */
interface RuleFormData {
  rule_key: string
  rule_value_str: string
  rule_value_num: number
  rule_value_bool: boolean
}

export function useQualityRule() {
  const loading = ref(false)
  const rules = ref<QualityRuleItem[]>([])
  const projects = ref<Project[]>([])
  const selectedProjectId = ref<number | null>(null)

  // 编辑对话框状态
  const dialogVisible = ref(false)
  const currentRule = ref<QualityRuleItem | null>(null)
  const formRef = ref()
  const formData = reactive<RuleFormData>({
    rule_key: '',
    rule_value_str: '',
    rule_value_num: 0,
    rule_value_bool: false,
  })

  /** 根据规则类型获取当前编辑值 */
  const currentRuleValue = computed<string | number | boolean>(() => {
    const rule = currentRule.value
    if (!rule) return ''
    switch (rule.value_type) {
      case 'boolean':
        return formData.rule_value_bool
      case 'number':
        return formData.rule_value_num
      case 'enum':
        return formData.rule_value_str
      default:
        return formData.rule_value_str
    }
  })

  /** 表单校验规则 */
  const formRules = computed(() => ({
    rule_value_str: [
      { required: true, message: '请输入规则值', trigger: 'blur' },
    ],
  }))

  /** 加载项目列表 */
  const loadProjects = async (): Promise<void> => {
    try {
      const response = await ProjectAPI.getProjects({ page: 1, page_size: 100 })
      projects.value = response.data?.items ?? []
      if (projects.value.length > 0 && !selectedProjectId.value) {
        selectedProjectId.value = projects.value[0].id
        await loadRules()
      }
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '获取项目列表失败'
      ElMessage.error(msg)
    }
  }

  /** 加载质量规则列表 */
  const loadRules = async (): Promise<void> => {
    if (!selectedProjectId.value) {
      rules.value = []
      return
    }
    loading.value = true
    try {
      const response = await qualityRuleApi.getQualityRules(selectedProjectId.value)
      rules.value = Array.isArray(response.data) ? response.data : []
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '获取质量规则失败'
      ElMessage.error(msg)
    } finally {
      loading.value = false
    }
  }

  /** 项目切换 */
  const handleProjectChange = (): void => {
    loadRules()
  }

  /** 格式化规则值用于表格展示 */
  const formatRuleValue = (value: string | number | boolean): string => {
    if (typeof value === 'boolean') return value ? '是' : '否'
    return String(value)
  }

  /** 判断当前值是否为默认值 */
  const isDefaultValue = (row: QualityRuleItem): boolean => {
    return row.rule_value === row.default_value
  }

  /** 打开编辑对话框 */
  const openEditDialog = (row: QualityRuleItem): void => {
    currentRule.value = row
    formData.rule_key = row.rule_key
    // 根据规则类型填充对应字段
    switch (row.value_type) {
      case 'boolean':
        formData.rule_value_bool = Boolean(row.rule_value)
        break
      case 'number':
        formData.rule_value_num = Number(row.rule_value)
        break
      default:
        formData.rule_value_str = String(row.rule_value)
        break
    }
    dialogVisible.value = true
  }

  /** 保存规则修改 */
  const saveRule = async (): Promise<void> => {
    if (!formRef.value) return
    await formRef.value.validate(async (valid: boolean) => {
      if (!valid) return
      if (!selectedProjectId.value) return
      try {
        await qualityRuleApi.updateQualityRule(selectedProjectId.value, {
          rule_key: formData.rule_key,
          rule_value: currentRuleValue.value,
        })
        ElMessage.success('规则更新成功')
        dialogVisible.value = false
        await loadRules()
      } catch (error: unknown) {
        const msg = error instanceof Error ? error.message : '更新规则失败'
        ElMessage.error(msg)
      }
    })
  }

  /** 恢复默认值 */
  const resetToDefault = (row: QualityRuleItem): void => {
    ElMessageBox.confirm(
      `确定要将规则「${row.rule_key}」恢复为默认值「${formatRuleValue(row.default_value)}」吗？`,
      '恢复默认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
      .then(async () => {
        if (!selectedProjectId.value) return
        try {
          await qualityRuleApi.updateQualityRule(selectedProjectId.value, {
            rule_key: row.rule_key,
            rule_value: row.default_value,
          })
          ElMessage.success('已恢复默认值')
          await loadRules()
        } catch (error: unknown) {
          const msg = error instanceof Error ? error.message : '恢复默认值失败'
          ElMessage.error(msg)
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
    loading,
    rules,
    projects,
    selectedProjectId,
    dialogVisible,
    currentRule,
    formRef,
    formData,
    formRules,
    handleProjectChange,
    formatRuleValue,
    isDefaultValue,
    openEditDialog,
    saveRule,
    resetToDefault,
  }
}
