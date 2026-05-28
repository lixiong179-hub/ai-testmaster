import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { caseApi, type QualityAnalysisResult } from '@/api/case'
import projectApi, { type Project } from '@/api/project'
import { optimizeCaseLocators, getProjectCostSummary, batchAnalyzeCases } from '@/api/caseQuality'

interface CostSummary {
  total_tokens: number
  total_api_calls: number
  estimated_cost: number
  [key: string]: unknown
}

export function useCaseQualityAnalysis() {
  const loading = ref(false)
  const projects = ref<Project[]>([])
  const selectedProjectId = ref<number | undefined>(undefined)
  const analysisResult = ref<QualityAnalysisResult | null>(null)
  const dialogVisible = ref(false)
  const dialogContent = ref('')
  const costSummary = ref<CostSummary | null>(null)
  const costLoading = ref(false)
  const batchAnalyzing = ref(false)

  const overallScore = computed(() => analysisResult.value?.overall_score ?? 0)
  const scoreLevel = computed(() => {
    const s = overallScore.value
    return s >= 80 ? 'success' : s >= 60 ? 'warning' : 'danger'
  })
  const scoreLabel = computed(() => {
    const s = overallScore.value
    return s >= 80 ? '优秀' : s >= 60 ? '良好' : '需改进'
  })

  async function loadProjects(): Promise<void> {
    try {
      const response = await projectApi.getProjects({ page: 1, page_size: 100 })
      projects.value = response.data.items
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '加载项目失败')
    }
  }

  async function fetchAnalysis(): Promise<void> {
    if (!selectedProjectId.value) return
    loading.value = true
    try {
      analysisResult.value = await caseApi.getQualityAnalysis(selectedProjectId.value)
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '加载质量分析失败')
      analysisResult.value = null
    } finally {
      loading.value = false
    }
  }

  async function loadCostSummary(): Promise<void> {
    if (!selectedProjectId.value) return
    costLoading.value = true
    try {
      const res = await getProjectCostSummary(selectedProjectId.value)
      costSummary.value = res.data as CostSummary
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '加载成本统计失败')
    } finally {
      costLoading.value = false
    }
  }

  async function handleBatchAnalyze(caseIds: number[]): Promise<void> {
    if (!caseIds.length) {
      ElMessage.warning('请选择要分析的用例')
      return
    }
    batchAnalyzing.value = true
    try {
      await batchAnalyzeCases(caseIds)
      ElMessage.success('批量分析完成')
      if (selectedProjectId.value) await fetchAnalysis()
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '批量分析失败')
    } finally {
      batchAnalyzing.value = false
    }
  }

  async function handleOptimizeLocators(caseId: number): Promise<void> {
    try {
      await optimizeCaseLocators(caseId)
      ElMessage.success('定位器优化完成')
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '优化定位器失败')
    }
  }

  async function handleProjectChange(): Promise<void> {
    analysisResult.value = null
    costSummary.value = null
    if (selectedProjectId.value) {
      await Promise.all([fetchAnalysis(), loadCostSummary()])
    }
  }

  function showDetail(content: string): void {
    dialogContent.value = content
    dialogVisible.value = true
  }

  onMounted(loadProjects)

  return {
    loading,
    projects,
    selectedProjectId,
    analysisResult,
    dialogVisible,
    dialogContent,
    overallScore,
    scoreLevel,
    scoreLabel,
    handleProjectChange,
    fetchAnalysis,
    showDetail,
    costSummary,
    costLoading,
    loadCostSummary,
    batchAnalyzing,
    handleBatchAnalyze,
    handleOptimizeLocators,
  }
}
