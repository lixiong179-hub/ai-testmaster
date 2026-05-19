/**
 * 单元格编辑 Composable
 * 职责：技术视图表格中双击单元格的内联编辑（操作/预期结果/XPath）
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { testCaseApi } from '@/api/case'
import type { TechnicalView } from '@/api/testCaseView'

/** 当前正在编辑的单元格信息 */
export interface EditingCell {
  stepIndex: number
  field: string
}

export function useCellEdit(
  caseId: { value: number },
  technicalViewData: { value: TechnicalView | null },
  issueType: { value: string }
) {
  const editingCell = ref<EditingCell | null>(null)
  const editingValue = ref('')
  const cellSaving = ref(false)

  /** 开始编辑某个单元格 */
  const startCellEdit = (stepIndex: number, field: string, value: unknown) => {
    if (issueType.value === 'product_bug') return
    editingCell.value = { stepIndex, field }
    editingValue.value = (value as string) || ''
  }

  /** 取消单元格编辑 */
  const cancelCellEdit = () => {
    editingCell.value = null
    editingValue.value = ''
  }

  /** 保存单元格编辑内容到后端 */
  const saveCellEdit = async () => {
    if (!editingCell.value || !technicalViewData.value) return

    const { stepIndex, field } = editingCell.value
    const step = technicalViewData.value.steps[stepIndex]
    if (!step) return

    if (!editingValue.value.trim() && (field === 'action' || field === 'expected_result')) {
      ElMessage.warning('内容不能为空')
      return
    }

    cellSaving.value = true
    try {
      const stepId = step.step_id || step.step_number

      if (field === 'action' || field === 'expected_result') {
        const stepsPayload = technicalViewData.value.steps.map((s, i) => ({
          step_number: s.step_number,
          action: i === stepIndex && field === 'action' ? editingValue.value : s.action || '',
          expected_result:
            i === stepIndex && field === 'expected_result'
              ? editingValue.value
              : s.expected_result || '',
        }))
        await testCaseApi.updateCase(caseId.value, { steps: stepsPayload })
      } else if (field === 'css_selector' || field === 'xpath') {
        await testCaseApi.updateStepLocator(stepId, {
          [field]: editingValue.value,
        })
      }

      // 本地同步更新视图数据
      if (field === 'action') {
        step.action = editingValue.value
        step.description = editingValue.value
      }
      else if (field === 'expected_result') step.expected_result = editingValue.value
      else if (field === 'css_selector' && step.locator) step.locator.css_selector = editingValue.value
      else if (field === 'xpath' && step.locator) step.locator.xpath = editingValue.value

      ElMessage.success('保存成功')
      editingCell.value = null
      editingValue.value = ''
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } }; message?: string }
      console.error('保存失败:', error)
      ElMessage.error(err.response?.data?.detail || '保存失败')
    } finally {
      cellSaving.value = false
    }
  }

  return {
    editingCell,
    editingValue,
    cellSaving,
    startCellEdit,
    cancelCellEdit,
    saveCellEdit,
  }
}
