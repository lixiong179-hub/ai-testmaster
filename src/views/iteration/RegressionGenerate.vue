<template>
  <div class="regression-generate-container">
    <div class="page-header">
      <el-button @click="goBack" :icon="ArrowLeft" circle size="small" />
      <h2>旧项目变更分析</h2>
      <el-tag v-if="precheckData" :type="precheckData.can_run ? 'success' : 'danger'" size="large">
        {{ precheckData.can_run ? '满足运行条件' : '暂不满足条件' }}
      </el-tag>
    </div>

    <el-row :gutter="20" v-loading="precheckLoading">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>项目信息</span>
              <el-tag size="small" type="primary">项目 #{{ projectId }}</el-tag>
            </div>
          </template>
          <div class="info-row">
            <span class="info-label">UI 原型名称</span>
            <span class="info-value">{{ prototypeName }}</span>
          </div>
          <div class="info-row" v-if="precheckData">
            <span class="info-label">可用 UI 页面</span>
            <span class="info-value">{{ precheckData.ui.parsed_screen_count }} 个已解析</span>
            <el-tag v-if="precheckData.ui.unparsed_screen_count > 0" type="warning" size="small">
              另有 {{ precheckData.ui.unparsed_screen_count }} 个未解析
            </el-tag>
          </div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>历史用例扫描范围</span>
            </div>
          </template>
          <div v-if="precheckData" class="scan-stats">
            <div class="scan-stat-row">
              <span class="stat-label">总历史用例</span>
              <span class="stat-value">{{ precheckData.history_cases.total }}</span>
            </div>
            <div class="scan-stat-row highlight">
              <span class="stat-label">参与扫描</span>
              <span class="stat-value">{{ precheckData.history_cases.included }}</span>
            </div>
            <div class="scan-stat-row">
              <span class="stat-label">active</span>
              <span class="stat-value">{{ precheckData.history_cases.active }}</span>
            </div>
            <div class="scan-stat-row">
              <span class="stat-label">draft</span>
              <span class="stat-value">{{ precheckData.history_cases.draft }}</span>
            </div>
            <div class="scan-stat-row">
              <span class="stat-label">待评审</span>
              <span class="stat-value">{{ precheckData.history_cases.pending_review }}</span>
            </div>
            <div class="scan-stat-row excluded">
              <span class="stat-label">已排除(archived)</span>
              <span class="stat-value">{{ precheckData.history_cases.archived }}</span>
            </div>
            <div class="scan-stat-row excluded">
              <span class="stat-label">已排除(已删除)</span>
              <span class="stat-value">{{ precheckData.history_cases.deleted }}</span>
            </div>
          </div>
          <div v-else class="empty-hint">
            <el-empty description="暂无数据" :image-size="60" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="config-card" v-if="precheckData">
      <template #header>
        <div class="card-header">
          <span>配置与启动</span>
        </div>
      </template>

      <el-form label-width="120px">
        <el-form-item label="迭代">
          <div class="iteration-select-row">
            <el-select
              v-model="selectedIterationId"
              placeholder="选择已有迭代（或创建新迭代）"
              style="width: 320px"
              filterable
              clearable
            >
              <el-option
                v-for="it in iterations"
                :key="it.id"
                :label="`${it.name}${it.version ? ' (' + it.version + ')' : ''}`"
                :value="it.id"
              />
            </el-select>
            <el-button type="primary" plain @click="showCreateIteration = true">
              创建新迭代
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="测试点" v-if="precheckData.test_points.total > 0">
          <el-select
            v-model="selectedTestPointIds"
            multiple
            filterable
            placeholder="选择测试点（可选，建议选择以获得更精确的对齐结果）"
            style="width: 100%"
            collapse-tags
            collapse-tags-tooltip
          >
            <el-option
              v-for="tp in testPoints"
              :key="tp.id"
              :label="`${tp.module} - ${tp.point}`"
              :value="tp.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="变更说明">
          <el-input
            v-model="changeNotes"
            type="textarea"
            :rows="2"
            placeholder="可选：输入本次变更的简要说明（如新增了哪些功能、修改了哪些页面）"
          />
        </el-form-item>
      </el-form>

      <el-alert
        v-if="precheckData.blocking_reasons.length > 0"
        :title="precheckData.blocking_reasons.join('；')"
        type="error"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />

      <el-alert
        v-for="(w, idx) in precheckData.warnings"
        :key="idx"
        :title="w"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 8px"
      />

      <el-alert
        title="历史用例会自动扫描，不需要手动逐条选择旧用例。场景 4 会自动扫描当前项目下非 archived、未删除的历史用例。"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />

      <div class="start-section">
        <el-button
          type="danger"
          size="large"
          :disabled="!canStart"
          :loading="starting"
          @click="handleStart"
        >
          开始旧项目变更分析
        </el-button>
        <span v-if="!selectedIterationId" class="start-hint">请先选择或创建一个迭代</span>
        <span v-else-if="!precheckData.can_run" class="start-hint">不满足运行条件</span>
        <span v-else class="start-hint">
          将调用场景 4 Pipeline，分析 {{ precheckData.history_cases.included }} 个历史用例
        </span>
      </div>
    </el-card>

    <el-dialog
      v-model="showCreateIteration"
      title="创建新迭代"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="newIterationForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="newIterationForm.name" placeholder="如：v2.0 首页重构" />
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="newIterationForm.version" placeholder="如：2.0.0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="newIterationForm.description"
            type="textarea"
            :rows="2"
            placeholder="迭代描述（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateIteration = false">取消</el-button>
        <el-button type="primary" :loading="creatingIteration" @click="handleCreateIteration">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { pipelineApi } from '@/api/pipeline'
import type { Scenario4PrecheckResponse } from '@/api/pipeline'
import { iterationApi } from '@/api/iteration'
import type { Iteration } from '@/api/iteration'
import { testPointApi } from '@/api/testPoint'
import type { TestPoint } from '@/api/testPoint'

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

const canStart = computed(() => {
  return selectedIterationId.value && precheckData.value?.can_run
})

const goBack = () => {
  router.back()
}

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
    const response = await testPointApi.getList(projectId.value, {
      page: 1,
      page_size: 200,
    })
    testPoints.value = response?.items || []
  } catch {
    // 可选资源，失败不阻断
  }
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
  if (!newIterationForm.value.name.trim()) {
    ElMessage.warning('请输入迭代名称')
    return
  }
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
      } catch {
        return
      }
    }
  } catch {
    // 获取迭代详情失败不阻断
  }

  starting.value = true
  try {
    const prototypePayload = { screen_ids: precheckData.value.ui.usable_screen_ids }
    await iterationApi.addIterationInput(iterationId, {
      kind: 'prototype',
      payload: prototypePayload,
      hash: computeHash(prototypePayload),
    })

    if (selectedTestPointIds.value.length > 0) {
      const tpPayload = { test_point_ids: selectedTestPointIds.value }
      await iterationApi.addIterationInput(iterationId, {
        kind: 'testpoint',
        payload: tpPayload,
        hash: computeHash(tpPayload),
      })
    }

    if (changeNotes.value.trim()) {
      const notesPayload = { notes: changeNotes.value.trim() }
      await iterationApi.addIterationInput(iterationId, {
        kind: 'change_notes',
        payload: notesPayload,
        hash: computeHash(notesPayload),
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
</script>

<style scoped>
.regression-generate-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  flex: 1;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.info-row:last-child {
  border-bottom: none;
}

.info-label {
  color: #909399;
  width: 100px;
  flex-shrink: 0;
}

.info-value {
  font-weight: 500;
}

.scan-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scan-stat-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid #f5f5f5;
}

.scan-stat-row:last-child {
  border-bottom: none;
}

.scan-stat-row.highlight {
  background: #f0f9eb;
  padding: 6px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.scan-stat-row.excluded .stat-value {
  color: #c0c4cc;
}

.scan-stat-row.excluded .stat-label {
  color: #c0c4cc;
}

.config-card {
  margin-top: 20px;
}

.iteration-select-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.start-section {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 20px;
}

.start-hint {
  color: #909399;
  font-size: 13px;
}

.empty-hint {
  padding: 20px;
}
</style>
