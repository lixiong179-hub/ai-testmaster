import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { caseApi, type QualityAnalysisResult } from '@/api/case'
import projectApi, { type Project } from '@/api/project'

export function useCaseQualityAnalysis() {
  const loading = ref(false)
  const projects = ref<Project[]>([])
  const selectedProjectId = ref<number | undefined>(undefined)
  const analysisResult = ref<QualityAnalysisResult | null>(null)
  const dialogVisible = ref(false)
  const dialogContent = ref('')

  const overallScore = computed(() => analysisResult.value?.overall_score ?? 0)
  const scoreLevel = computed(() => { const s = overallScore.value; return s >= 80 ? 'success' : s >= 60 ? 'warning' : 'danger' })
  const scoreLabel = computed(() => { const s = overallScore.value; return s >= 80 ? '优秀' : s >= 60 ? '良好' : '需改进' })

  async function loadProjects(): Promise<void> {
    try {
      const response = await projectApi.getProjects({ page: 1, page_size: 100 })
      projects.value = response.data.items
    } catch (error) { ElMessage.error(error instanceof Error ? error.message : '加载项目失败') }
  }

  async function fetchAnalysis(): Promise<void> {
    if (!selectedProjectId.value) return
    loading.value = true
    try {
      analysisResult.value = await caseApi.getQualityAnalysis(selectedProjectId.value)
    } catch (error) { ElMessage.error(error instanceof Error ? error.message : '加载质量分析失败'); analysisResult.value = null }
    finally { loading.value = false }
  }

  async function handleProjectChange(): Promise<void> {
    analysisResult.value = null
    if (selectedProjectId.value) { await fetchAnalysis() }
  }

  function showDetail(content: string): void { dialogContent.value = content; dialogVisible.value = true }

  onMounted(loadProjects)

  return {
    loading, projects, selectedProjectId, analysisResult, dialogVisible,
    dialogContent, overallScore, scoreLevel, scoreLabel, handleProjectChange,
    fetchAnalysis, showDetail,
  }
}
