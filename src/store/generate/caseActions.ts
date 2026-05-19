import { ElMessage, ElMessageBox } from 'element-plus'
import caseApi from '@/api/case'
import { useFlowSortStore } from '@/store/flowSort'
import type { GeneratedStep } from './types'
import type { GenerateState } from './state'
import type { GenerateComputed } from './computed'
import type { StoreActions } from './types'

export function createCaseActions(
  state: GenerateState,
  computed: GenerateComputed,
  getActions: () => StoreActions
) {
  const handleRegenerateCase = async (
    index: number,
    skipConfirm: boolean = false,
    preserveGenerating: boolean = false
  ) => {
    const c = state.generatedCases.value[index]
    if (!c) return

    if (!skipConfirm) {
      try {
        await ElMessageBox.confirm(
          `将重新生成用例"${c.title}"，当前内容将被覆盖，是否继续？`,
          '确认重新生成',
          { confirmButtonText: '重新生成', cancelButtonText: '取消', type: 'warning' }
        )
      } catch {
        return
      }
    }

    state.generating.value = true
    state.progress.value = 10
    state.progressText.value = '正在调用AI重新生成...'

    try {
      const flowSortStore = useFlowSortStore()
      const apiData: Record<string, unknown> = {
        project_id: Number(state.formData.project_id),
        description: state.formData.scene || `重新生成用例"${c.title}"`,
        case_type: state.formData.case_type || c.case_type,
        exec_mode: state.formData.exec_mode || 'all',
        priority: state.formData.priority || c.priority || 2,
        enhanced_mode: state.formData.enhanced_mode !== undefined ? state.formData.enhanced_mode : true,
        extra_requirements: state.formData.extra_requirements || '',
        mode: flowSortStore.nodes.length > 0 ? ('graph' as const) : ('linear' as const),
        flow_sort_data:
          flowSortStore.nodes.length > 0
            ? {
                nodes: [...flowSortStore.nodes]
                  .sort((a, b) => (a.main_order ?? 999) - (b.main_order ?? 999))
                  .map((n, idx) => ({
                    screen_id: n.screen_id,
                    screen_order: idx + 1,
                    flow_type: n.flow_type,
                    main_order: n.main_order,
                    screen_name: n.screen_name,
                    ui_spec_elements: n.ui_spec_elements || [],
                    summary: n.summary || '',
                    flow_meta: n.flow_meta || undefined,
                  })),
                edges: flowSortStore.edges.map((e) => ({
                  source: String(e.source),
                  target: String(e.target),
                  edge_type: e.edge_type,
                  condition: e.condition || '',
                  label: e.label || '',
                  trigger_action: e.trigger_action || '',
                  pre_action: e.pre_action || '',
                  note: e.note || '',
                })),
                module_info: computed.flowSortModuleInfo.value,
              }
            : undefined,
        context: {
          base_case: {
            title: c.title,
            module: c.module,
            precondition: c.precondition,
            steps: c.steps || [],
            expected_result: c.expected_result,
          },
          requirement_content: state.contextPreview.value?.requirement_content || '',
          ui_description: (state.lastContext.value as Record<string, string>).ui_description || '',
          ui_specs: (state.lastContext.value as Record<string, unknown[]>).ui_specs || [],
          test_points: state.contextPreview.value?.test_points || [],
          history_cases: (state.lastContext.value as Record<string, unknown[]>).history_cases || [],
        },
      }

      const casesArray = await caseApi.aiGenerateCaseEnhanced(
        apiData as unknown as import('@/api/case').TestCaseAIEnhancedRequest
      )
      const casesData = Array.isArray(casesArray) ? casesArray : [casesArray]
      const caseData = casesData[0]
      if (!caseData) {
        throw new Error('AI 未返回有效用例数据')
      }

      const oldDbId = c._dbId

      state.generatedCases.value[index] = {
        ...state.generatedCases.value[index],
        title: caseData.title || caseData.name || '',
        module: caseData.module || '',
        case_type: caseData.case_type || caseData.type || '',
        precondition: caseData.precondition || '',
        test_data: caseData.test_data,
        steps: (caseData.steps || []) as GeneratedStep[],
        expected_result: caseData.expected_result || '',
        priority: caseData.priority || state.formData.priority,
        ai_change_type: caseData.change_type || 'added',
        parent_case_id: caseData.parent_case_id ?? null,
        _error: undefined,
        _saved: false,
        _dbId: undefined,
      }

      state.progressText.value = '正在保存...'
      const saved = await getActions().saveSingleCaseToDb(state.generatedCases.value[index])
      if (!saved) {
        state.generatedCases.value[index]._error = '保存失败'
      }

      if (oldDbId && saved) {
        try {
          await caseApi.deleteCase(oldDbId)
        } catch {
          console.warn(`[handleRegenerateCase] 删除旧用例 #${oldDbId} 失败，可能产生冗余数据`)
        }
      }

      state.progress.value = 100
      state.progressText.value = '重新生成完成！'
      ElMessage.success('用例重新生成成功')
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      ElMessage.error(
        err.response?.data?.detail || err.response?.data?.message || err.message || '重新生成失败'
      )
    } finally {
      if (!preserveGenerating) {
        state.generating.value = false
      }
    }
  }

  const handleDeleteCase = async (index: number) => {
    const c = state.generatedCases.value[index]
    if (!c) return

    try {
      await ElMessageBox.confirm(`确定要删除用例"${c.title}"吗？删除后不可恢复。`, '确认删除', {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      })
    } catch {
      return
    }

    if (c._dbId) {
      try {
        await caseApi.deleteCase(c._dbId)
      } catch (e) {
        console.error(`[handleDeleteCase] 删除数据库用例 #${c._dbId} 失败:`, e)
        ElMessage.error('数据库删除失败，请稍后重试')
        return
      }
    }

    state.generatedCases.value.splice(index, 1)
    state.selectedCaseIndices.value = new Set(
      [...state.selectedCaseIndices.value].filter((i) => i !== index).map((i) => (i > index ? i - 1 : i))
    )

    if (state.generatedCases.value.length === 0) {
      state.currentCaseIndex.value = -1
    } else if (state.currentCaseIndex.value >= state.generatedCases.value.length) {
      state.currentCaseIndex.value = state.generatedCases.value.length - 1
    }

    ElMessage.success('用例已删除')
  }

  const handleRegenerateSelected = async () => {
    const indices = [...state.selectedCaseIndices.value].sort((a, b) => a - b)
    if (indices.length === 0) {
      ElMessage.warning('请先选择要重新生成的用例')
      return
    }

    try {
      await ElMessageBox.confirm(
        `将重新生成选中的 ${indices.length} 条用例，当前内容将被覆盖，是否继续？`,
        '确认批量重新生成',
        { confirmButtonText: '重新生成', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }

    state.generating.value = true
    try {
      for (const idx of indices) {
        await getActions().handleRegenerateCase(idx, true, true)
        if (!state.generating.value) break
      }
    } finally {
      state.generating.value = false
    }
  }

  const handleDeleteSelected = async () => {
    const indices = [...state.selectedCaseIndices.value].sort((a, b) => b - a)
    if (indices.length === 0) {
      ElMessage.warning('请先选择要删除的用例')
      return
    }

    try {
      await ElMessageBox.confirm(
        `确定要删除选中的 ${indices.length} 条用例吗？删除后不可恢复。`,
        '确认批量删除',
        { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }

    const dbIds = indices
      .map((i) => state.generatedCases.value[i]?._dbId)
      .filter((id): id is number => id !== undefined)

    if (dbIds.length > 0) {
      try {
        await caseApi.batchDeleteCases(dbIds)
      } catch (e) {
        console.error('[handleDeleteSelected] 批量删除数据库用例失败:', e)
        ElMessage.error('数据库批量删除失败，请稍后重试')
        return
      }
    }

    for (const idx of indices) {
      state.generatedCases.value.splice(idx, 1)
    }

    state.selectedCaseIndices.value = new Set()

    if (state.generatedCases.value.length === 0) {
      state.currentCaseIndex.value = -1
    } else if (state.currentCaseIndex.value >= state.generatedCases.value.length) {
      state.currentCaseIndex.value = state.generatedCases.value.length - 1
    }

    ElMessage.success(`已删除 ${indices.length} 条用例`)
  }

  const handleCancel = () => {
    if (!state.generating.value) return
    ElMessageBox.confirm('确定要取消生成吗？', '取消确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(() => {
      state.generating.value = false
      state.progressText.value = '已取消'
      state.errorMessage.value = ''
      ElMessage.info('生成已取消')
    })
  }

  return {
    handleRegenerateCase,
    handleDeleteCase,
    handleRegenerateSelected,
    handleDeleteSelected,
    handleCancel,
  }
}
