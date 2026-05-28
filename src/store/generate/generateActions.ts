import { ElMessage, ElMessageBox } from 'element-plus'
import { type ApiResponse } from '@/utils/request'
import { caseApi } from '@/api/case'
import type { TestPoint } from '@/api/testPoint'
import type { GenerateState } from './state'
import type { GenerateComputed } from './computed'
import type { StoreActions } from './types'
import {
  generateForTestPoints,
  generateForFlowNodes,
  type FlowSortEditorRef,
} from './generateHelpers'
import { useFlowSortStore } from '@/store/flowSort'

export function createGenerateActions(
  state: GenerateState,
  computed: GenerateComputed,
  getActions: () => StoreActions
) {
  const generateErrorSuggestions = () => {
    const error = state.errorMessage.value.toLowerCase()
    if (
      error.includes('认证') ||
      error.includes('authentication') ||
      (error.includes('api') && error.includes('key')) ||
      error.includes('503') ||
      error.includes('无效')
    ) {
      state.errorSuggestions.value = [
        '请检查 .env 文件中的 DEEPSEEK_API_KEY 是否配置正确',
        '访问 https://platform.deepseek.com/ 获取有效的 API Key',
        '确保 API Key 没有过期或被禁用',
        '如果问题持续，请联系管理员检查 DeepSeek 服务状态',
      ]
      return
    }
    if (
      error.includes('429') ||
      error.includes('rate limit') ||
      error.includes('频率') ||
      error.includes('过多')
    ) {
      state.errorSuggestions.value = [
        'AI服务请求频率过高，请稍后重试',
        '建议降低请求频率或等待一段时间后再试',
        '可以尝试分批生成测试用例',
      ]
      return
    }
    state.errorSuggestions.value = [
      '请确保输入的测试场景描述清晰具体',
      '建议先配置需求文档和UI原型图链接',
      '检查网络连接是否正常',
      '稍后重试，可能是API服务暂时不可用',
      '如果问题持续，请联系管理员',
    ]
  }

  const showValidationDialog = (validation: {
    errors: string[]
    warnings: string[]
  }): Promise<boolean> => {
    state.issueDialogValidation.value = validation
    state.issueDialogVisible.value = true
    return new Promise((resolve) => {
      state.issueDialogResolver.value = resolve
    })
  }

  const onIssueDialogConfirm = () => {
    state.issueDialogVisible.value = false
    state.issueDialogResolver.value?.(true)
    state.issueDialogResolver.value = null
  }

  const onIssueDialogCancel = () => {
    state.issueDialogVisible.value = false
    state.issueDialogResolver.value?.(false)
    state.issueDialogResolver.value = null
  }

  const handleGenerate = async (flowSortEditorRef: FlowSortEditorRef | null) => {
    if (!computed.canGenerate.value) {
      ElMessage.warning('请先选择测试点、需求文档、UI原型图或历史用例')
      return
    }

    if (state.selectedUiPrototypeProjectId.value && state.uiScreens.value.length > 0) {
      const flowSortStore = useFlowSortStore()
      if (flowSortStore.quickMode === false) {
        const validation = flowSortEditorRef?.getFlowValidationIssues?.()
        if (validation?.errors.length) {
          const confirmed = await showValidationDialog(validation)
          if (!confirmed) return
        }
        if (validation?.warnings.length) {
          const confirmed = await showValidationDialog({
            errors: [],
            warnings: validation.warnings,
          })
          if (!confirmed) return
        }
      }
    }

    const targetPoints =
      state.formData.test_point_ids.length > 0
        ? state.formData.test_point_ids
        : (state.contextPreview.value?.test_points || []).map((tp) => tp.id)

    const MAX_COUNT = 20
    if (targetPoints.length > MAX_COUNT) {
      try {
        await ElMessageBox.confirm(
          `当前选择了 ${targetPoints.length} 个测试点，将逐个生成用例，可能需要较长时间。是否继续？`,
          '确认生成',
          { confirmButtonText: '继续生成', cancelButtonText: '取消', type: 'warning' }
        )
      } catch {
        return
      }
    }
    if (targetPoints.length === 0) {
      try {
        await ElMessageBox.confirm(
          '将基于选中的历史用例、需求文档和UI原型直接生成测试用例，是否继续？',
          '确认生成',
          { confirmButtonText: '继续生成', cancelButtonText: '取消', type: 'warning' }
        )
      } catch {
        return
      }
    }

    state.generatedCases.value = []
    state.currentCaseIndex.value = -1
    state.errorMessage.value = ''
    state.errorSuggestions.value = []
    state.generating.value = true
    state.progress.value = 0
    state.progressText.value =
      targetPoints.length > 0
        ? `准备生成 ${targetPoints.length} 条测试用例...`
        : '准备生成测试用例...'
    state.currentStep.value = 2

    try {
      let context: Record<string, unknown> = {
        requirement_content: '',
        ui_description: '',
        test_points: [],
        project_config: null,
      }

      state.progress.value = 5
      state.progressText.value = '正在准备生成上下文...'

      if (state.formData.project_id) {
        const contextResponse = (await caseApi.generateContext({
          project_id: Number(state.formData.project_id),
          requirement_file_ids:
            state.formData.requirement_file_ids.length > 0
              ? state.formData.requirement_file_ids
              : undefined,
          ui_file_ids:
            state.formData.ui_file_ids.length > 0 ? state.formData.ui_file_ids : undefined,
          ui_screen_ids:
            state.formData.ui_screen_ids.length > 0 ? state.formData.ui_screen_ids : undefined,
          test_point_ids: targetPoints.length > 0 ? targetPoints : undefined,
          history_case_ids:
            state.selectedHistoryCaseIds.value.length > 0
              ? state.selectedHistoryCaseIds.value
              : state.selectedHistoryCaseIds.value.length === 0 &&
                  state._historyCaseUserCleared.value
                ? []
                : undefined,
        })) as unknown as ApiResponse<{
          requirement_content?: string
          ui_descriptions?: unknown[]
          ui_specs?: unknown[]
          test_points?: TestPoint[]
          project_config?: unknown
          history_cases?: unknown[]
        }>

        if (contextResponse?.data) {
          const data = contextResponse.data
          const contextTestPoints = targetPoints.length > 0 ? data.test_points || [] : []
          context = {
            requirement_content: data.requirement_content || '',
            ui_descriptions: data.ui_descriptions || [],
            ui_description: JSON.stringify(data.ui_descriptions || []),
            ui_specs: data.ui_specs || [],
            test_points: contextTestPoints,
            project_config: data.project_config || null,
            history_cases: data.history_cases || [],
          }
          state.lastContext.value = { ...context }

          state.progress.value = 15
          state.progressText.value = '上下文准备完成，开始构建生成数据...'
        }
      }

      if (targetPoints.length > 0) {
        await generateForTestPoints(
          state,
          computed,
          getActions,
          context,
          targetPoints,
          flowSortEditorRef
        )
      } else {
        await generateForFlowNodes(state, computed, getActions, context, flowSortEditorRef)
      }

      if (!state.generating.value) {
        state.progressText.value = `已取消，已生成 ${state.generatedCases.value.length} 条`
      } else {
        state.currentCaseIndex.value = 0
        state.progress.value = 100
        state.progressText.value = `生成完成！共 ${state.generatedCases.value.length} 条`
        const failCount = state.generatedCases.value.filter((c) => c._error).length
        if (failCount === 0) {
          ElMessage.success(`成功生成 ${state.generatedCases.value.length} 条测试用例`)
        } else {
          ElMessage.warning(
            `生成完成：${state.generatedCases.value.length - failCount} 成功，${failCount} 失败`
          )
        }
      }
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      state.progress.value = 100
      state.progressText.value = '生成失败'
      state.errorMessage.value =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        'AI生成测试用例失败'
      generateErrorSuggestions()
      ElMessage.error(state.errorMessage.value)
    } finally {
      state.generating.value = false
    }
  }

  return {
    generateErrorSuggestions,
    showValidationDialog,
    onIssueDialogConfirm,
    onIssueDialogCancel,
    handleGenerate,
  }
}
