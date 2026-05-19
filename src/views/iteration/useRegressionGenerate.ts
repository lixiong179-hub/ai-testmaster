import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { pipelineApi } from '@/api/pipeline'
import type { Scenario4PrecheckResponse } from '@/api/pipeline'
import { iterationApi } from '@/api/iteration'
import type { Iteration } from '@/api/iteration'
import { testPointApi } from '@/api/testPoint'
import type { TestPoint } from '@/api/testPoint'

export function useRegressionGenerate() {
  const router = useRouter()
  const route = useRoute()

  const projectId = computed(() => Number(route.query.project_id || 0))
  const uiProjectId = computed(() => Number(route.query.ui_project_id || 0))
  const prototypeName = computed(() => String(route.query.name || 'UI原型'))

  const precheckLoading = ref(false)
  const precheckData = ref<Scenario4PrecheckResponse | null>(null)

  const iterations = ref<Iteration[]>([])
  const selectedIterationId = ref<number | ''>('')
  const showCreateIteration = ref(false)
  const creatingIteration = ref(false)
  const newIterationForm = ref({ name: '', version: '', description: '' })

  const testPoints = ref<TestPoint[]>([])
  const selectedTestPointIds = ref<number[]>([])
  const changeNotes = ref('')
  const starting = ref(false)

  const computeHash = (data: unknown): string => {
    const str = JSON.stringify(data, Object.keys(data as Record<string, unknown>).sort())
    let hash = 0
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i)
      hash = ((hash << 5) - hash) + char
      hash = hash & hash
    }
    return Math.abs(hash).toString(16).padStart(8, '0')
  }

  const canStart = computed(() => selectedIterationId.value && precheckData.value?.can_run)

  const goBack = () => { router.back() }

  const loadIterations = async () => {
    if (!projectId.value) return
    try {
      const response = await iterationApi.getIterations(projectId.value)
      iterations.value = response.data.items || []
    } catch {
      ElMessage.warning('加载迭代列表失败')
    }
  }

  const loadTestPoints = async () => {
    if (!projectId.value) return
    try {
      const response = await testPointApi.getList(projectId.value, { page: 1, page_size: 200 })
      testPoints.value = response?.items || []
    } catch { /* optional resource */ }
  }

  const loadPrecheck = async () => {
    precheckLoading.value = true
    try {
      const response = await pipelineApi.precheckScenario4({
        project_id: projectId.value,
        ui_project_id: uiProjectId.value || undefined,
        test_point_ids: selectedTestPointIds.value.length > 0 ? selectedTestPointIds.value : undefined,
      })
      precheckData.value = response.data
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      ElMessage.error(err?.response?.data?.detail || '预检失败')
    } finally {
      precheckLoading.value = false
    }
  }

  const handleCreateIteration = async () => {
    if (!newIterationForm.value.name.trim()) { ElMessage.warning('请输入迭代名称'); return }
    creatingIteration.value = true
    try {
      const response = await iterationApi.createIteration({
        project_id: projectId.value,
        name: newIterationForm.value.name.trim(),
        version: newIterationForm.value.version || undefined,
        description: newIterationForm.value.description || undefined,
      })
      iterations.value.push(response.data)
      selectedIterationId.value = response.data.id
      showCreateIteration.value = false
      newIterationForm.value = { name: '', version: '', description: '' }
      ElMessage.success('迭代创建成功')
    } catch {
      ElMessage.error('创建迭代失败')
    } finally {
      creatingIteration.value = false
    }
  }

  const handleStart = async () => {
    if (!selectedIterationId.value || !precheckData.value) return
    const iterationId = selectedIterationId.value as number

    try {
      const existingInputsResponse = await iterationApi.getIteration(iterationId)
      const it = existingInputsResponse.data as Iteration & { pipeline_runs?: Array<{ id: number }> }
      if (it.pipeline_runs && it.pipeline_runs.length > 0) {
        try {
          await ElMessageBox.confirm(
            '该迭代已运行过 Pipeline，重新运行会生成新的 PipelineRun，并可能产生新的用例结果。是否继续？',
            '确认重新运行',
            { confirmButtonText: '继续', cancelButtonText: '取消', type: 'warning' }
          )
        } catch { return }
      }
    } catch { /* get iteration detail failure not blocking */ }

    starting.value = true
    try {
      const prototypePayload = { screen_ids: precheckData.value.ui.usable_screen_ids }
      await iterationApi.addIterationInput(iterationId, {
        kind: 'prototype', payload: prototypePayload, hash: computeHash(prototypePayload),
      })

      if (selectedTestPointIds.value.length > 0) {
        const tpPayload = { test_point_ids: selectedTestPointIds.value }
        await iterationApi.addIterationInput(iterationId, {
          kind: 'testpoint', payload: tpPayload, hash: computeHash(tpPayload),
        })
      }

      if (changeNotes.value.trim()) {
        const notesPayload = { notes: changeNotes.value.trim() }
        await iterationApi.addIterationInput(iterationId, {
          kind: 'change_notes', payload: notesPayload, hash: computeHash(notesPayload),
        })
      }

      const response = await pipelineApi.runPipeline(iterationId, { scenario: 4 })
      const runId = response.data.run_id || response.data.pipeline_run_id
      ElMessage.success('场景 4 Pipeline 已启动')
      router.push(`/home/case/pipeline/${runId}`)
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      ElMessage.error(err?.response?.data?.detail || '启动场景 4 失败')
    } finally {
      starting.value = false
    }
  }

  onMounted(async () => {
    await Promise.all([loadIterations(), loadTestPoints(), loadPrecheck()])
  })

  return {
    projectId, prototypeName, precheckLoading, precheckData,
    iterations, selectedIterationId, showCreateIteration, creatingIteration, newIterationForm,
    testPoints, selectedTestPointIds, changeNotes, starting, canStart,
    goBack, handleCreateIteration, handleStart,
  }
}
