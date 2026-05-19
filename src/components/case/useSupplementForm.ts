import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { caseApi, type TestCase } from '@/api/case'

export interface SupplementResponse {
  test_case?: TestCase
  inferred_capabilities?: { name: string; description: string }[]
  questions?: { question: string }[]
  change_summary?: { field: string; old_value: string; new_value: string }[]
}

export function useSupplementForm(caseId: number, projectId: number) {
  const loading = ref(false)
  const saving = ref(false)
  const activeTab = ref('inferred')
  const inferredCapabilities = ref<{ name: string; description: string; selected: boolean }[]>([])
  const customCapabilities = ref<{ name: string; description: string }[]>([])
  const questions = ref<{ question: string; answer: string }[]>([])
  const supplementResult = ref<SupplementResponse | null>(null)
  const showResult = ref(false)
  const originalCase = ref<TestCase | null>(null)
  const changeSummary = ref<{ field: string; old_value: string; new_value: string }[]>([])

  const hasInferredCapabilities = computed(() => inferredCapabilities.value.length > 0)
  const selectedInferredCount = computed(() => inferredCapabilities.value.filter((c) => c.selected).length)
  const hasCustomCapabilities = computed(() => customCapabilities.value.some((c) => c.name.trim()))
  const hasQuestions = computed(() => questions.value.some((q) => q.answer.trim()))
  const canSubmit = computed(() => selectedInferredCount.value > 0 || hasCustomCapabilities.value || hasQuestions.value)

  async function fetchSupplementData(): Promise<void> {
    loading.value = true
    try {
      // 后端暂无 supplement 端点，使用用例详情作为基础数据
      const response = await caseApi.getCaseDetail(caseId)
      originalCase.value = response as unknown as TestCase
      inferredCapabilities.value = []
      questions.value = []
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '加载补充数据失败')
    } finally {
      loading.value = false
    }
  }

  function addCustomCapability(): void {
    customCapabilities.value.push({ name: '', description: '' })
  }

  function removeCustomCapability(index: number): void {
    customCapabilities.value.splice(index, 1)
  }

  function toggleInferredCapability(index: number): void {
    inferredCapabilities.value[index].selected = !inferredCapabilities.value[index].selected
  }

  function selectAllInferred(): void {
    inferredCapabilities.value.forEach((c) => { c.selected = true })
  }

  function deselectAllInferred(): void {
    inferredCapabilities.value.forEach((c) => { c.selected = false })
  }

  async function handleSubmit(): Promise<void> {
    if (!canSubmit.value) { ElMessage.warning('请至少选择一项补充内容'); return }
    saving.value = true
    try {
      const payload = buildPayload()
      // 后端暂无 supplement 端点，使用用例更新接口
      await caseApi.updateCase(caseId, payload as any)
      showResult.value = true
      ElMessage.success('补充完成')
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '补充失败')
    } finally {
      saving.value = false
    }
  }

  function buildPayload(): Record<string, unknown> {
    const selectedCapabilities = inferredCapabilities.value.filter((c) => c.selected)
    const customCaps = customCapabilities.value.filter((c) => c.name.trim())
    const answeredQuestions = questions.value.filter((q) => q.answer.trim())
    return {
      project_id: projectId,
      inferred_capabilities: selectedCapabilities.map((c) => ({ name: c.name, description: c.description })),
      custom_capabilities: customCaps.map((c) => ({ name: c.name, description: c.description })),
      questions: answeredQuestions.map((q) => ({ question: q.question, answer: q.answer })),
    }
  }

  function reset(): void {
    inferredCapabilities.value = []
    customCapabilities.value = []
    questions.value = []
    supplementResult.value = null
    showResult.value = false
    changeSummary.value = []
    activeTab.value = 'inferred'
  }

  onMounted(fetchSupplementData)

  return {
    loading, saving, activeTab, inferredCapabilities, customCapabilities,
    questions, supplementResult, showResult, originalCase, changeSummary,
    hasInferredCapabilities, selectedInferredCount, hasCustomCapabilities,
    hasQuestions, canSubmit, fetchSupplementData, addCustomCapability,
    removeCustomCapability, toggleInferredCapability, selectAllInferred,
    deselectAllInferred, handleSubmit, reset,
  }
}
