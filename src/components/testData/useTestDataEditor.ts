import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  testDataApi,
  dataTypeOptions,
  generationRuleOptions,
  DataType,
  GenerationRule,
  type TestData,
} from '@/api/testData'
import type { TagType } from '@/types/element-plus'

export function useTestDataEditor(
  props: { stepId: number; stepAction?: string },
  emit: (e: 'update', data: TestData[]) => void
) {
  const loading = ref(false)
  const generating = ref(false)
  const autoGenerating = ref(false)
  const testDataList = ref<(TestData & { isEditing?: boolean; isNew?: boolean })[]>([])
  const generatedData = ref<Record<string, any>>({})

  const fetchTestData = async () => {
    if (!props.stepId) return
    loading.value = true
    try {
      const response = await testDataApi.getByStepId(props.stepId)
      testDataList.value = response.data_list.map((item) => ({ ...item, isEditing: false }))
      emit('update', testDataList.value)
    } catch (error) {
      ElMessage.error('获取测试数据失败')
    } finally {
      loading.value = false
    }
  }

  const handleAdd = () => {
    testDataList.value.push({
      id: 0,
      step_id: props.stepId,
      field_name: '',
      field_type: DataType.TEXT,
      generation_rule: GenerationRule.RANDOM,
      data_value: null,
      rule_config: null,
      min_length: null,
      max_length: null,
      min_value: null,
      max_value: null,
      enum_values: null,
      description: '',
      is_required: true,
      sort_order: testDataList.value.length,
      isEditing: true,
      isNew: true,
    })
  }

  const handleEdit = (row: TestData & { isEditing?: boolean }) => {
    row.isEditing = true
  }

  const handleSave = async (row: TestData & { isEditing?: boolean; isNew?: boolean }) => {
    if (!row.field_name) {
      ElMessage.warning('请输入字段名称')
      return
    }
    try {
      const saveData = {
        step_id: row.step_id,
        field_name: row.field_name,
        field_type: row.field_type as DataType,
        generation_rule: row.generation_rule as GenerationRule,
        data_value: row.data_value || undefined,
        rule_config: row.rule_config || undefined,
        min_length: row.min_length || undefined,
        max_length: row.max_length || undefined,
        min_value: row.min_value || undefined,
        max_value: row.max_value || undefined,
        enum_values: row.enum_values || undefined,
        description: row.description || undefined,
        is_required: row.is_required,
        sort_order: row.sort_order,
      }
      if (row.isNew) {
        const response = await testDataApi.create(saveData)
        Object.assign(row, response)
        row.isNew = false
        ElMessage.success('创建成功')
      } else {
        const response = await testDataApi.update(row.id, saveData)
        Object.assign(row, response)
        ElMessage.success('更新成功')
      }
      row.isEditing = false
      emit('update', testDataList.value)
    } catch (error) {
      ElMessage.error('保存失败')
    }
  }

  const handleCancel = (
    row: TestData & { isEditing?: boolean; isNew?: boolean },
    index: number
  ) => {
    if (row.isNew) {
      testDataList.value.splice(index, 1)
    } else {
      row.isEditing = false
      fetchTestData()
    }
  }

  const handleDelete = async (row: TestData) => {
    try {
      await ElMessageBox.confirm('确定删除该测试数据吗？', '提示', { type: 'warning' })
      await testDataApi.delete(row.id)
      ElMessage.success('删除成功')
      fetchTestData()
    } catch (error) {
      if (error !== 'cancel') ElMessage.error('删除失败')
    }
  }

  const handleGenerateAll = async () => {
    if (testDataList.value.length === 0) {
      ElMessage.warning('没有测试数据可生成')
      return
    }
    generating.value = true
    try {
      const response = await testDataApi.generate(props.stepId)
      generatedData.value = response.generated_data
      ElMessage.success('数据生成成功')
    } catch (error) {
      ElMessage.error('数据生成失败')
    } finally {
      generating.value = false
    }
  }

  const handleAutoGenerate = async () => {
    if (!props.stepAction) {
      ElMessage.warning('步骤操作描述为空，无法智能生成')
      return
    }
    autoGenerating.value = true
    try {
      const response = await testDataApi.autoGenerate(props.stepId, props.stepAction)
      if (response.count > 0) {
        ElMessage.success(`成功生成 ${response.count} 个测试数据字段`)
        fetchTestData()
      } else ElMessage.info('未识别到需要生成的测试数据')
    } catch (error) {
      ElMessage.error('智能生成失败')
    } finally {
      autoGenerating.value = false
    }
  }

  const handleCopy = () => {
    const jsonStr = JSON.stringify(generatedData.value, null, 2)
    navigator.clipboard
      .writeText(jsonStr)
      .then(() => ElMessage.success('已复制到剪贴板'))
      .catch(() => ElMessage.error('复制失败'))
  }

  const getDataTypeLabel = (type: string) =>
    dataTypeOptions.find((opt) => opt.value === type)?.label || type
  const getDataTypeTagType = (type: string): TagType => {
    const typeMap: Record<string, TagType> = {
      text: 'primary',
      email: 'success',
      phone: 'success',
      number: 'warning',
      date: 'info',
      datetime: 'info',
      boolean: 'primary',
      url: 'success',
      username: 'primary',
      password: 'danger',
      id_card: 'warning',
    }
    return typeMap[type] || 'primary'
  }
  const getGenerationRuleLabel = (rule: string) =>
    generationRuleOptions.find((opt) => opt.value === rule)?.label || rule

  watch(
    () => props.stepId,
    () => {
      fetchTestData()
      generatedData.value = {}
    },
    { immediate: true }
  )

  return {
    loading,
    generating,
    autoGenerating,
    testDataList,
    generatedData,
    fetchTestData,
    handleAdd,
    handleEdit,
    handleSave,
    handleCancel,
    handleDelete,
    handleGenerateAll,
    handleAutoGenerate,
    handleCopy,
    getDataTypeLabel,
    getDataTypeTagType,
    getGenerationRuleLabel,
  }
}
