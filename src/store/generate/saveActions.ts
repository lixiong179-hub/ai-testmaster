import { ElMessage } from 'element-plus'
import caseApi from '@/api/case'
import type { TestCaseApiStep } from '@/api/case'
import { generateCaseNo, normalizePriority } from './types'
import type { GeneratedStep, SaveSingleCaseParam } from './types'
import type { GenerateState } from './state'
import type { GenerateComputed } from './computed'

export function createSaveActions(state: GenerateState, computed: GenerateComputed) {
  const buildStepsPayload = (steps: GeneratedStep[] | undefined): TestCaseApiStep[] => {
    return (steps || []).map((s: GeneratedStep, i: number) => ({
      step: String(s.step || i + 1),
      action: s.action || '',
      param: s.input_value || s.param || '',
      expected_result: s.expected_result || '',
      action_type: s.action_type || '',
      input_value: s.input_value || '',
      target_element: s.target_element || '',
      ui_elements: s.ui_elements || [],
    }))
  }

  const buildCaseCreatePayload = (c: {
    id?: number
    title?: string
    module?: string
    case_type?: string
    precondition?: string
    steps?: GeneratedStep[]
    expected_result?: string
    priority?: number
    test_category?: string
    test_data?: Record<string, unknown>
    parent_case_id?: number | null
    ai_change_type?: 'added' | 'modified' | 'deprecated'
    test_point_id?: number | null
  }) => {
    const stepsPayload = buildStepsPayload(c.steps)
    const priority = normalizePriority(c.priority ?? 2)
    return {
      project_id: Number(state.formData.project_id),
      test_point_id: c.test_point_id ?? undefined,
      case_no: generateCaseNo(state.formData.project_id, c.id),
      title: c.title || '未命名测试用例',
      module: c.module || '默认模块',
      case_type: c.case_type || '',
      precondition: c.precondition || '系统已通过配置自动登录至目标页面',
      steps:
        stepsPayload.length > 0
          ? stepsPayload
          : [{ step: 1, action: '执行测试', param: '预期结果正常' }],
      expected_result: c.expected_result || '操作成功',
      priority,
      test_category: c.test_category || c.case_type || '',
      test_data: (c.test_data || {}) as Record<
        string,
        Record<string, string | number | boolean | null>
      >,
      generate_status: 1,
      parent_case_id: c.parent_case_id ?? undefined,
      ai_change_type: c.ai_change_type || undefined,
    }
  }

  const saveSingleCaseToDb = async (c: SaveSingleCaseParam): Promise<boolean> => {
    try {
      const payload = buildCaseCreatePayload(c)
      const created = await caseApi.createCase(payload)
      c._saved = true
      c._dbId = created.id
      return true
    } catch (e) {
      console.error(`[saveSingleCaseToDb] 用例 "${c.title}" 保存失败:`, e)
      return false
    }
  }

  const handleSaveCase = async () => {
    const caseToSave = state.isEditingResult.value
      ? state.editingCase.value
      : computed.viewingCase.value
    if (!caseToSave) {
      ElMessage.warning('没有可保存的用例')
      return
    }
    if ('_error' in caseToSave && caseToSave._error) {
      ElMessage.warning('该用例生成失败，无法保存，请重新生成')
      return
    }
    if (!state.formData.project_id) {
      ElMessage.warning('请先选择项目')
      return
    }

    state.saving.value = true
    try {
      const currentCase = computed.viewingCase.value
      const dbId = currentCase?._dbId

      const payload = buildCaseCreatePayload({
        title: caseToSave.title,
        module: caseToSave.module,
        case_type: caseToSave.case_type,
        precondition: caseToSave.precondition,
        steps: caseToSave.steps,
        expected_result: caseToSave.expected_result,
        priority: caseToSave.priority,
        test_category: caseToSave.test_category,
        test_data: caseToSave.test_data,
        parent_case_id: caseToSave.parent_case_id,
        ai_change_type: caseToSave.ai_change_type,
        test_point_id: currentCase?.test_point_id,
      })

      if (dbId) {
        const updatePayload: import('@/api/case').TestCaseUpdateData = {
          title: caseToSave.title,
          module: caseToSave.module,
          case_type: caseToSave.case_type,
          precondition: caseToSave.precondition,
          steps: (caseToSave.steps || []).map((s, i) => ({
            step_number: typeof s.step === 'number' ? s.step : i + 1,
            action: s.action || '',
            expected_result: s.expected_result || '',
            param: s.input_value || s.param || '',
          })),
          expected_result: caseToSave.expected_result,
          priority: payload.priority,
          test_category: caseToSave.test_category || caseToSave.case_type,
        }
        await caseApi.updateCase(dbId, updatePayload)
        ElMessage.success(`"${caseToSave.title}" 更新成功`)
      } else {
        const created = await caseApi.createCase(payload)
        ElMessage.success(`"${caseToSave.title}" 保存成功`)
        if (
          state.currentCaseIndex.value >= 0 &&
          state.currentCaseIndex.value < state.generatedCases.value.length
        ) {
          state.generatedCases.value[state.currentCaseIndex.value]._saved = true
          state.generatedCases.value[state.currentCaseIndex.value]._dbId = created.id
        }
      }

      const wasEditing = state.isEditingResult.value

      state.isEditingResult.value = false
      if (
        state.currentCaseIndex.value >= 0 &&
        state.currentCaseIndex.value < state.generatedCases.value.length
      ) {
        const target = state.generatedCases.value[state.currentCaseIndex.value]
        target._saved = true
        if (wasEditing) {
          target.title = caseToSave.title
          target.module = caseToSave.module
          target.case_type = caseToSave.case_type
          target.precondition = caseToSave.precondition
          target.expected_result = caseToSave.expected_result
          target.priority = caseToSave.priority
          target.steps = caseToSave.steps
          if (caseToSave.test_data) {
            target.test_data = caseToSave.test_data
          }
        }
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      const detail = err.response?.data?.detail
      ElMessage.error(detail && typeof detail === 'string' ? detail : '保存失败，请检查必填字段')
    } finally {
      state.saving.value = false
    }
  }

  return {
    buildStepsPayload,
    buildCaseCreatePayload,
    saveSingleCaseToDb,
    handleSaveCase,
  }
}
