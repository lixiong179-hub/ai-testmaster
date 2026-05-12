/**
 * 失败分析 Composable
 * 职责：失败步骤分析、用例纠正、问题类型管理
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { analyzeFailure, type FailureAnalysisResult } from '@/api/testExecution'

/** 问题类型标签映射 */
export const ISSUE_TYPE_LABELS: Record<string, string> = {
  case_issue: '用例问题',
  product_bug: 'Bug问题',
  needs_review: '待人工判断',
}

/** 问题类型颜色映射 */
export const ISSUE_TYPE_COLORS: Record<string, string> = {
  case_issue: 'warning',
  product_bug: 'danger',
  needs_review: 'info',
}

export type IssueType = 'case_issue' | 'product_bug' | 'needs_review'

export interface UseFailureAnalysisOptions {
  /** 执行状态（用于获取case_id） */
  executionStatus: import('vue').Ref<Record<string, unknown> | null>
}

export function useFailureAnalysis(options: UseFailureAnalysisOptions) {
  const router = useRouter()

  /** 每个步骤索引对应的失败分析结果 */
  const failureAnalysisMap = ref<Record<number, FailureAnalysisResult>>({})

  /** 分析请求加载状态 */
  const analysisLoading = ref(false)

  /** 每个步骤索引对应的问题类型 */
  const issueTypeMap = ref<Record<number, IssueType>>({})

  /**
   * 分析失败步骤
   * @param step 失败步骤数据
   * @param index 步骤索引
   */
  const handleAnalyzeFailure = async (step: Record<string, unknown>, index: number) => {
    if (failureAnalysisMap.value[index]) return
    analysisLoading.value = true
    try {
      const resultId = (step.result_id || step.id) as number | undefined
      if (!resultId) {
        ElMessage.warning('无法获取执行结果ID，请稍后重试')
        analysisLoading.value = false
        return
      }
      const res = await analyzeFailure(resultId)
      const resAny = res as unknown as Record<string, unknown>
      const resData = resAny.data as Record<string, unknown> | undefined
      const data = (resData?.data as FailureAnalysisResult | undefined) ??
        (resData as unknown as FailureAnalysisResult | undefined)
      if (data) {
        failureAnalysisMap.value[index] = data
        issueTypeMap.value[index] = data.suggested_type
      }
    } catch (error: unknown) {
      console.error('分析失败原因出错:', error)
      const errResp = (error as Record<string, unknown>)?.response as
        | Record<string, unknown>
        | undefined
      const detail = (errResp?.data as Record<string, unknown>)?.detail as string | undefined
      ElMessage.error(detail || '分析失败原因出错')
    } finally {
      analysisLoading.value = false
    }
  }

  /**
   * 纠正用例 - 跳转至用例详情页
   * @param step 失败步骤数据
   * @param index 步骤索引
   */
  const handleCorrectCase = (step: Record<string, unknown>, index: number) => {
    if (issueTypeMap.value[index] === 'product_bug') {
      ElMessage.warning('这是Bug问题，不允许修改用例！')
      return
    }
    const caseId =
      (step.case_id as number | undefined) ??
      (options.executionStatus.value?.case_id as number | undefined)
    if (!caseId) {
      ElMessage.warning('无法获取用例ID')
      return
    }
    const analysis = failureAnalysisMap.value[index]
    const query: Record<string, string> = {
      correction: 'true',
      stepIndex: String(index),
      issueType: issueTypeMap.value[index] || 'case_issue',
    }
    if (analysis) {
      query.failureReason = encodeURIComponent(analysis.reason || '')
      query.aiAnalysis = encodeURIComponent(analysis.ai_analysis || '')
    }
    router.push({
      path: `/home/case/detail/${caseId}`,
      query,
    })
  }

  return {
    failureAnalysisMap,
    analysisLoading,
    issueTypeMap,
    handleAnalyzeFailure,
    handleCorrectCase,
  }
}
