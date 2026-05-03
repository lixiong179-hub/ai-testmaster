<template>
  <div v-loading="loading" class="supplement-form" element-loading-text="加载 AI 反推摘要...">
    <div v-if="error" class="error-state">
      <el-alert :title="error" type="error" show-icon :closable="false" />
      <el-button style="margin-top: 16px" @click="fetchSummary" :loading="loading">
        重新加载
      </el-button>
    </div>

    <div v-else-if="summary" class="supplement-content">
      <el-alert
        v-if="summary.needs_confirmation"
        title="AI 反推置信度不足，请逐项确认"
        type="warning"
        show-icon
        :closable="false"
        style="margin-bottom: 16px"
      />

      <el-descriptions :column="2" border size="small" class="summary-meta">
        <el-descriptions-item label="分析模式">
          <el-tag :type="summary.is_old_project ? 'warning' : 'success'" size="small">
            {{ summary.is_old_project ? '旧项目变更分析' : '新项目能力反推' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="置信度">
          <el-progress
            :percentage="Math.round(summary.confidence * 100)"
            :status="summary.confidence >= 0.7 ? 'success' : 'warning'"
            :stroke-width="16"
            style="max-width: 180px"
          />
        </el-descriptions-item>
        <el-descriptions-item label="分析摘要" :span="2">
          {{ summary.analysis_summary || '无' }}
        </el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">
        <el-icon><Collection /></el-icon>
        {{ summary.is_old_project ? '变更摘要' : '推断的业务能力' }}
      </el-divider>

      <div v-if="summary.is_old_project && summary.change_summary" class="change-summary">
        <el-collapse v-model="changeActive">
          <el-collapse-item title="新增能力" name="new" v-if="summary.change_summary.new_capabilities.length > 0">
            <div
              v-for="(cap, i) in summary.change_summary.new_capabilities"
              :key="'new-' + i"
              class="capability-card"
            >
              <el-checkbox
                v-model="cap._confirmed"
                :label="`${cap.name} (${cap.key})`"
                size="large"
              />
              <p class="cap-desc">{{ cap.description }}</p>
              <el-tag size="small" type="info">置信度: {{ Math.round((cap.confidence || 0) * 100) }}%</el-tag>
              <p class="cap-evidence" v-if="cap.supporting_evidence">
                <el-icon><InfoFilled /></el-icon> {{ cap.supporting_evidence }}
              </p>
            </div>
          </el-collapse-item>

          <el-collapse-item
            title="变更能力"
            name="modified"
            v-if="summary.change_summary.modified_capabilities.length > 0"
          >
            <div
              v-for="(cap, i) in summary.change_summary.modified_capabilities"
              :key="'mod-' + i"
              class="capability-card"
            >
              <el-checkbox v-model="cap._confirmed" size="large">
                <span class="old-name">{{ cap.old_name }}</span>
                <el-icon><Right /></el-icon>
                <span>{{ cap.new_name }}</span>
              </el-checkbox>
              <p class="cap-desc">{{ cap.change_description }}</p>
              <el-tag size="small" :type="cap.change_type === 'business_logic' ? 'warning' : 'info'">
                {{ cap.change_type === 'business_logic' ? '业务逻辑变更' : cap.change_type === 'both' ? 'UI+业务变更' : '纯UI变更' }}
              </el-tag>
            </div>
          </el-collapse-item>

          <el-collapse-item
            title="移除能力"
            name="removed"
            v-if="summary.change_summary.removed_capabilities.length > 0"
          >
            <div
              v-for="(cap, i) in summary.change_summary.removed_capabilities"
              :key="'rem-' + i"
              class="capability-card"
            >
              <el-checkbox v-model="cap._confirmed" :label="`${cap.old_name} (${cap.old_key})`" size="large" />
              <el-tag size="small" type="danger">置信度: {{ Math.round((cap.confidence || 0) * 100) }}%</el-tag>
            </div>
          </el-collapse-item>
        </el-collapse>

        <p class="ui-only-note" v-if="summary.change_summary.ui_only_changes">
          <el-icon><InfoFilled /></el-icon> {{ summary.change_summary.ui_only_changes }}
        </p>
      </div>

      <div v-else class="inferred-capabilities">
        <div
          v-for="(cap, i) in summary.inferred_capabilities"
          :key="'cap-' + i"
          class="capability-card"
        >
          <div class="cap-header">
            <el-checkbox
              v-model="cap._confirmed"
              size="large"
              class="cap-check"
            />
            <div class="cap-info">
              <span class="cap-name">{{ cap.name }}</span>
              <el-tag size="small" type="info" class="cap-key">{{ cap.key }}</el-tag>
              <el-tag
                size="small"
                :type="cap.confidence >= 0.8 ? 'success' : cap.confidence >= 0.5 ? 'warning' : 'danger'"
              >
                置信度: {{ Math.round(cap.confidence * 100) }}%
              </el-tag>
            </div>
          </div>
          <p class="cap-desc">{{ cap.description }}</p>
          <p class="cap-evidence" v-if="cap.supporting_evidence">
            <el-icon><InfoFilled /></el-icon> {{ cap.supporting_evidence }}
          </p>
          <div class="cap-edit">
            <el-input
              v-if="!cap._confirmed"
              v-model="cap._name_edit"
              placeholder="修改能力名称"
              size="small"
              style="max-width: 240px"
            />
            <el-input
              v-if="!cap._confirmed"
              v-model="cap._desc_edit"
              placeholder="修改能力描述"
              size="small"
              type="textarea"
              :rows="2"
              style="max-width: 400px; margin-top: 8px"
            />
          </div>
        </div>

        <div class="add-capability" v-if="canAddCapability">
          <el-button type="primary" plain @click="addNewCapability" :disabled="newCapCount >= 5">
            <el-icon><Plus /></el-icon> 添加业务能力
          </el-button>
          <div v-for="(cap, i) in newCapabilities" :key="'new-' + i" class="capability-card new-cap">
            <el-input v-model="cap.name" placeholder="能力名称" size="small" style="margin-bottom: 8px" />
            <el-input v-model="cap.key" placeholder="唯一标识 (snake_case)" size="small" style="margin-bottom: 8px" />
            <el-input
              v-model="cap.description"
              placeholder="能力描述"
              size="small"
              type="textarea"
              :rows="2"
              style="margin-bottom: 8px"
            />
            <el-button type="danger" size="small" text @click="removeNewCapability(i)">
              <el-icon><Delete /></el-icon> 移除
            </el-button>
          </div>
        </div>
      </div>

      <el-divider content-position="left">
        <el-icon><QuestionFilled /></el-icon>
        AI 的疑问（{{ summary.uncertain_questions?.length || 0 }} 个）
      </el-divider>

      <div v-if="summary.uncertain_questions?.length > 0" class="questions-section">
        <div
          v-for="(q, i) in summary.uncertain_questions"
          :key="'q-' + i"
          class="question-card"
        >
          <div class="q-header">
            <span class="q-num">{{ i + 1 }}.</span>
            <span class="q-text">{{ q.question }}</span>
          </div>
          <p class="q-context" v-if="q.context">
            <el-tag size="small" type="info">来源: {{ q.context }}</el-tag>
          </p>
          <p class="q-suggested" v-if="q.suggested_answer">
            <el-icon><ChatLineSquare /></el-icon> AI 建议: {{ q.suggested_answer }}
          </p>
          <el-input
            v-model="q._answer"
            type="textarea"
            :rows="2"
            placeholder="请输入你的回答..."
            :disabled="!q.question"
          />
        </div>
      </div>
      <el-empty v-else description="AI 没有疑问，所有推断都很确定" :image-size="80" />

      <el-divider />
      <el-input
        v-model="notes"
        type="textarea"
        :rows="2"
        placeholder="补充说明（可选）"
        maxlength="500"
        show-word-limit
      />

      <div class="form-actions">
        <el-button @click="handleReset">重置修改</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">
          <el-icon><CircleCheck /></el-icon> 保存补全结果
        </el-button>
      </div>
    </div>

    <el-empty v-else-if="!loading" description="暂无反推摘要数据" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  Collection,
  InfoFilled,
  Right,
  Plus,
  Delete,
  QuestionFilled,
  ChatLineSquare,
  CircleCheck,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { pipelineApi } from '@/api/pipeline'
import type { InferredSummary } from '@/api/pipeline'

const props = defineProps<{
  runId: number
}>()

const emit = defineEmits<{
  saved: [runId: number]
  reset: []
}>()

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const summary = ref<InferredSummary | null>(null)
const notes = ref('')
const changeActive = ref<string[]>([])
const newCapabilities = ref<Array<{ name: string; key: string; description: string }>>([])

const newCapCount = computed(() => newCapabilities.value.length)
const canAddCapability = computed(() => !summary.value?.is_old_project)

function prepareCapabilities() {
  if (!summary.value) return
  summary.value.inferred_capabilities.forEach((cap) => {
    cap._confirmed = (cap.confidence ?? 0) >= 0.7
    cap._name_edit = ''
    cap._desc_edit = ''
  })
}

function prepareChangeSummary() {
  if (!summary.value?.change_summary) return
  ;[...summary.value.change_summary.new_capabilities,
    ...summary.value.change_summary.modified_capabilities,
    ...summary.value.change_summary.removed_capabilities].forEach((cap) => {
    cap._confirmed = (cap.confidence ?? 0) >= 0.7
  })
}

function prepareQuestions() {
  if (!summary.value?.uncertain_questions) return
  summary.value.uncertain_questions.forEach((q) => {
    q._answer = q.suggested_answer || ''
  })
}

async function fetchSummary() {
  loading.value = true
  error.value = ''
  try {
    const response = await pipelineApi.getInferredSummary(props.runId)
    summary.value = response.data
    prepareCapabilities()
    prepareChangeSummary()
    prepareQuestions()
    if (summary.value.change_summary) {
      const names: string[] = []
      if (summary.value.change_summary.new_capabilities.length > 0) names.push('new')
      if (summary.value.change_summary.modified_capabilities.length > 0) names.push('modified')
      if (summary.value.change_summary.removed_capabilities.length > 0) names.push('removed')
      changeActive.value = names
    }
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } }; message?: string }
    error.value = e.response?.data?.detail || e.message || '加载反推摘要失败'
  } finally {
    loading.value = false
  }
}

function addNewCapability() {
  newCapabilities.value.push({ name: '', key: '', description: '' })
}

function removeNewCapability(index: number) {
  newCapabilities.value.splice(index, 1)
}

function buildConfirmedCapabilities(): Array<Record<string, unknown>> {
  const result: Array<Record<string, unknown>> = []

  if (summary.value?.inferred_capabilities) {
    for (const cap of summary.value.inferred_capabilities) {
      if (!cap._confirmed && cap._name_edit) {
        result.push({ ...cap, name: cap._name_edit as string, key: cap.key || cap._name_edit as string, confirmed: false })
      } else if (cap._confirmed) {
        let desc = cap.description
        if (cap._desc_edit) desc = cap._desc_edit as string
        result.push({ ...cap, description: desc, confirmed: true })
      }
    }
  }

  for (const cap of newCapabilities.value) {
    if (cap.name && cap.key) {
      result.push({
        name: cap.name,
        key: cap.key,
        description: cap.description,
        confidence: 1.0,
        source: 'user_added',
        confirmed: true,
      })
    }
  }

  return result
}

function buildAnswers(): Array<Record<string, unknown>> {
  if (!summary.value?.uncertain_questions) return []
  return summary.value.uncertain_questions
    .map((q) => {
      const a = q._answer
      return a ? { question: q.question, context: q.context, answer: a } : null
    })
    .filter(Boolean) as Array<Record<string, unknown>>
}

function buildChangeSummary(): Record<string, unknown> | null {
  if (!summary.value?.change_summary) return null

  const cs = summary.value.change_summary
  return {
    new_capabilities: cs.new_capabilities.filter((c) => c._confirmed),
    modified_capabilities: cs.modified_capabilities.filter((c) => c._confirmed),
    removed_capabilities: cs.removed_capabilities.filter((c) => c._confirmed),
    ui_only_changes: cs.ui_only_changes,
  }
}

async function handleSave() {
  const confirmedCapabilities = buildConfirmedCapabilities()
  const answers = buildAnswers()
  const changeSummary = buildChangeSummary()

  if (confirmedCapabilities.length === 0 && answers.length === 0 && !changeSummary) {
    ElMessage.warning('请至少确认一项能力或回答一个问题')
    return
  }

  saving.value = true
  try {
    await pipelineApi.supplementSignals(props.runId, {
      confirmed_capabilities: confirmedCapabilities,
      answers,
      change_summary: changeSummary,
      notes: notes.value || null,
    })
    ElMessage.success('信号补全已保存')
    emit('saved', props.runId)
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } }; message?: string }
    ElMessage.error(e.response?.data?.detail || e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleReset() {
  try {
    await ElMessageBox.confirm('确定要重置所有修改？未保存的更改将丢失。', '确认重置', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    newCapabilities.value = []
    notes.value = ''
    if (summary.value) {
      prepareCapabilities()
      prepareChangeSummary()
      prepareQuestions()
    }
    emit('reset')
  } catch {
    // 用户取消
  }
}

onMounted(() => {
  fetchSummary()
})

watch(() => props.runId, (newVal) => {
  if (newVal) {
    error.value = ''
    summary.value = null
    newCapabilities.value = []
    notes.value = ''
    fetchSummary()
  }
})
</script>

<style scoped>
.supplement-form {
  min-height: 300px;
}

.error-state {
  padding: 40px;
  text-align: center;
}

.supplement-content {
  max-width: 860px;
  margin: 0 auto;
}

.summary-meta {
  margin-bottom: 24px;
}

.capability-card {
  padding: 16px;
  margin-bottom: 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
  transition: border-color 0.2s;
}

.capability-card:hover {
  border-color: var(--el-color-primary-light-5);
}

.cap-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.cap-check {
  margin-top: 2px;
}

.cap-info {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.cap-name {
  font-size: 15px;
  font-weight: 600;
}

.cap-key {
  font-family: monospace;
  font-size: 12px;
}

.cap-desc {
  margin: 8px 0 6px 0;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.5;
}

.cap-evidence {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin: 4px 0 0 0;
  display: flex;
  align-items: center;
  gap: 4px;
}

.cap-edit {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--el-border-color-lighter);
}

.old-name {
  text-decoration: line-through;
  color: var(--el-text-color-secondary);
}

.ui-only-note {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  margin: 12px 0 0 0;
}

.add-capability {
  margin-top: 16px;
}

.new-cap {
  margin-top: 12px;
  border-style: dashed;
}

.questions-section {
  margin-bottom: 16px;
}

.question-card {
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);
}

.q-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.q-num {
  color: var(--el-color-primary);
  font-weight: 600;
  min-width: 24px;
}

.q-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.q-context {
  margin: 4px 0;
}

.q-suggested {
  font-size: 13px;
  color: var(--el-color-warning);
  margin: 8px 0;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px;
  background: var(--el-color-warning-light-9);
  border-radius: 4px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}
</style>
