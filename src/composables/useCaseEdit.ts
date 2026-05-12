/**
 * 用例编辑状态管理 Composable
 * 职责：编辑模式切换、编辑表单初始化/保存/取消
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { testCaseApi } from '@/api/case'
import type { TestCase } from '@/types/testCase'

/** 编辑表单步骤项类型 */
export interface EditFormStep {
  _uid?: number
  step_number?: number
  action: string
  expected_result: string
  param?: string
}

/** 编辑表单类型 */
export interface EditForm {
  title: string
  module: string
  precondition: string
  expected_result: string
  priority: number
  case_type: string
  test_category: string
  steps: EditFormStep[]
}

export function useCaseEdit(
  caseItem: { value: TestCase | null },
  caseId: { value: number },
  fetchCaseDetail: () => Promise<void>
) {
  const isEditing = ref(false)
  const saving = ref(false)

  const editForm = ref<EditForm>({
    title: '',
    module: '',
    precondition: '',
    expected_result: '',
    priority: 2,
    case_type: '',
    test_category: '',
    steps: [],
  })

  /** 根据当前用例数据初始化编辑表单 */
  const initEditForm = () => {
    if (!caseItem.value) return

    editForm.value = {
      title: caseItem.value.title || '',
      module: caseItem.value.module || '',
      precondition: caseItem.value.precondition || '',
      expected_result: caseItem.value.expected_result || '',
      priority: caseItem.value.priority || 2,
      case_type: caseItem.value.case_type || '',
      test_category: caseItem.value.test_category || '',
      steps: caseItem.value.steps ? JSON.parse(JSON.stringify(caseItem.value.steps)) : [],
    }
  }

  /** 切换编辑状态（已编辑时取消，未编辑时进入编辑） */
  const toggleEdit = () => {
    if (isEditing.value) {
      cancelEdit()
    } else {
      isEditing.value = true
      initEditForm()
    }
  }

  /** 取消编辑并还原表单 */
  const cancelEdit = () => {
    isEditing.value = false
    initEditForm()
  }

  /** 保存编辑内容到后端 */
  const saveEdit = async () => {
    if (!editForm.value.title.trim()) {
      ElMessage.warning('请输入用例标题')
      return
    }
    if (editForm.value.steps.length === 0) {
      ElMessage.warning('请至少添加一个测试步骤')
      return
    }

    saving.value = true
    try {
      const updateData = {
        title: editForm.value.title,
        module: editForm.value.module,
        precondition: editForm.value.precondition,
        expected_result: editForm.value.expected_result,
        priority: editForm.value.priority,
        case_type: editForm.value.case_type,
        test_category: editForm.value.test_category,
        steps: editForm.value.steps,
      }

      await testCaseApi.updateCase(caseId.value, updateData)
      ElMessage.success('保存成功')
      isEditing.value = false

      // 重新获取数据
      await fetchCaseDetail()
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } }; message?: string }
      console.error('保存失败:', error)
      const errorMsg = err.response?.data?.detail || err.message || '保存失败'
      ElMessage.error(errorMsg)
    } finally {
      saving.value = false
    }
  }

  return {
    isEditing,
    saving,
    editForm,
    initEditForm,
    toggleEdit,
    cancelEdit,
    saveEdit,
  }
}
