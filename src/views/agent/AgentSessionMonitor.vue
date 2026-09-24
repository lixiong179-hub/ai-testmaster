<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  agentApi,
  agentStatusOptions,
  agentTypeOptions,
} from '@/api/agent'
import type {
  AgentAudit,
  AgentMessage,
  AgentSession,
  AgentStatus,
  AgentType,
} from '@/api/agent'

/**
 * Agent 会话监控（R1-3 可观测性闭环）。
 *
 * 三区块：会话列表 → 消息流 / 工具调用与成本。按需手动刷新，不做轮询。
 */

// ============== 会话列表 ==============

const sessions = ref<AgentSession[]>([])
const sessionsLoading = ref(false)
const filterType = ref<AgentType | ''>('')
const filterStatus = ref<AgentStatus | ''>('')
const selectedId = ref<number | null>(null)

const selectedSession = computed(() =>
  sessions.value.find((item) => item.id === selectedId.value) ?? null
)

async function loadSessions() {
  sessionsLoading.value = true
  try {
    const res = await agentApi.getSessions({
      agent_type: filterType.value || undefined,
      status: filterStatus.value || undefined,
      limit: 50,
    })
    if (res.code === 200) {
      sessions.value = res.data?.items ?? []
      // 选中项若已被过滤掉则清空
      if (selectedId.value && !sessions.value.some((s) => s.id === selectedId.value)) {
        selectedId.value = null
      }
    } else {
      ElMessage.error(res.msg || '会话列表加载失败')
    }
  } catch (err) {
    console.error('[AgentSessionMonitor] loadSessions failed:', err)
    ElMessage.error('会话列表加载失败')
  } finally {
    sessionsLoading.value = false
  }
}

// ============== 消息流与审计 ==============

const messages = ref<AgentMessage[]>([])
const audits = ref<AgentAudit[]>([])
const detailLoading = ref(false)

async function loadDetail(sessionId: number) {
  detailLoading.value = true
  try {
    const [msgRes, auditRes] = await Promise.all([
      agentApi.getMessages(sessionId),
      agentApi.getAudits(sessionId),
    ])
    messages.value = msgRes.code === 200 ? (msgRes.data ?? []) : []
    audits.value = auditRes.code === 200 ? (auditRes.data ?? []) : []
  } catch (err) {
    console.error('[AgentSessionMonitor] loadDetail failed:', err)
    ElMessage.error('会话明细加载失败')
  } finally {
    detailLoading.value = false
  }
}

watch(selectedId, (id) => {
  if (id) void loadDetail(id)
})

onMounted(() => {
  void loadSessions()
})

// ============== 展示辅助 ==============

const STATUS_TAG_TYPE: Record<string, 'success' | 'info' | 'danger' | 'warning'> = {
  completed: 'success',
  running: 'info',
  cancelled: 'info',
  failed: 'danger',
  loop_detected: 'warning',
  circuit_open: 'warning',
  token_exhausted: 'warning',
}

const APPROVAL_TEXT: Record<number, string> = { 0: '待审批', 1: '已批准', 2: '已拒绝' }

function statusTagType(status: AgentStatus) {
  return STATUS_TAG_TYPE[status] ?? 'info'
}

function statusLabel(status: AgentStatus) {
  return agentStatusOptions.find((o) => o.value === status)?.label ?? status
}

function typeLabel(agentType: AgentType) {
  return agentTypeOptions.find((o) => o.value === agentType)?.label ?? agentType
}

function formatTime(value: string | null) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

/** 耗时 = completed_at - started_at（秒），未完成时显示「进行中」 */
function durationText(session: AgentSession | null) {
  if (!session) return '—'
  if (!session.started_at) return '—'
  if (!session.completed_at) return '进行中'
  const seconds =
    (new Date(session.completed_at).getTime() -
      new Date(session.started_at).getTime()) / 1000
  if (Number.isNaN(seconds)) return '—'
  return `${seconds.toFixed(1)}s`
}

/** 消息内容统一渲染为文本：优先 text 字段，否则 JSON 化 */
function messageText(message: AgentMessage) {
  const text = (message.content as Record<string, unknown>)?.text
  if (typeof text === 'string' && text) return text
  return JSON.stringify(message.content, null, 2)
}

function auditDetailText(audit: AgentAudit) {
  const tool = (audit.action_detail as Record<string, unknown>)?.tool
  if (typeof tool === 'string' && tool) return tool
  return JSON.stringify(audit.action_detail)
}
</script>

<template>
  <div class="agent-monitor">
    <el-card class="agent-monitor__toolbar" shadow="never">
      <div class="agent-monitor__toolbar-inner">
        <span class="agent-monitor__title">Agent 会话监控</span>
        <el-select
          v-model="filterType"
          placeholder="Agent 类型"
          clearable
          style="width: 160px"
        >
          <el-option
            v-for="opt in agentTypeOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select
          v-model="filterStatus"
          placeholder="会话状态"
          clearable
          style="width: 160px"
        >
          <el-option
            v-for="opt in agentStatusOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-button type="primary" @click="loadSessions">刷新</el-button>
      </div>
    </el-card>

    <el-card class="agent-monitor__list" shadow="never">
      <el-table
        v-loading="sessionsLoading"
        :data="sessions"
        highlight-current-row
        height="260"
        @current-change="(row: AgentSession | null) => (selectedId = row?.id ?? null)"
      >
        <el-table-column prop="id" label="会话ID" width="90" />
        <el-table-column prop="project_id" label="项目ID" width="90" />
        <el-table-column label="Agent类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ typeLabel(row.agent_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTagType(row.status)">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" min-width="160">
          <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column prop="token_cost" label="Token" width="90" />
        <el-table-column prop="iteration_count" label="迭代" width="80" />
        <template #empty>
          <el-empty description="暂无 Agent 会话" :image-size="60" />
        </template>
      </el-table>
    </el-card>

    <div class="agent-monitor__detail" v-loading="detailLoading">
      <el-card class="agent-monitor__panel" shadow="never">
        <template #header>
          <div class="agent-monitor__panel-head">
            <span>消息流</span>
            <el-tag v-if="selectedSession" size="small" type="info">
              会话 #{{ selectedSession.id }} · {{ messages.length }} 条
            </el-tag>
          </div>
        </template>
        <el-empty
          v-if="!selectedSession"
          description="请选择上方会话查看消息流"
          :image-size="60"
        />
        <el-empty
          v-else-if="messages.length === 0"
          description="该会话暂无消息"
          :image-size="60"
        />
        <div v-else class="agent-monitor__messages">
          <div
            v-for="msg in messages"
            :key="msg.id"
            class="agent-monitor__message"
            :class="`agent-monitor__message--${msg.role}`"
          >
            <div class="agent-monitor__message-meta">
              <el-tag size="small" effect="dark">{{ msg.role }}</el-tag>
              <span v-if="msg.tool_name" class="agent-monitor__tool-name">
                {{ msg.tool_name }}
              </span>
              <span class="agent-monitor__message-time">{{ formatTime(msg.created_at) }}</span>
            </div>
            <pre class="agent-monitor__message-body">{{ messageText(msg) }}</pre>
          </div>
        </div>
      </el-card>

      <el-card class="agent-monitor__panel" shadow="never">
        <template #header>
          <div class="agent-monitor__panel-head">
            <span>工具调用与成本</span>
            <el-tag v-if="selectedSession" size="small" type="info">
              {{ audits.length }} 条审计
            </el-tag>
          </div>
        </template>
        <el-empty
          v-if="!selectedSession"
          description="请选择上方会话查看工具调用"
          :image-size="60"
        />
        <template v-else>
          <div class="agent-monitor__stats">
            <div class="agent-monitor__stat">
              <span class="agent-monitor__stat-label">Token 消耗</span>
              <span class="agent-monitor__stat-value">{{ selectedSession.token_cost }}</span>
            </div>
            <div class="agent-monitor__stat">
              <span class="agent-monitor__stat-label">耗时</span>
              <span class="agent-monitor__stat-value">{{ durationText(selectedSession) }}</span>
            </div>
            <div class="agent-monitor__stat">
              <span class="agent-monitor__stat-label">迭代轮数</span>
              <span class="agent-monitor__stat-value">
                {{ selectedSession.iteration_count }}
              </span>
            </div>
          </div>
          <el-empty
            v-if="audits.length === 0"
            description="该会话暂无工具调用记录"
            :image-size="60"
          />
          <el-table v-else :data="audits" size="small" max-height="320">
            <el-table-column prop="iteration" label="轮次" width="60" />
            <el-table-column prop="action_type" label="动作" width="130" />
            <el-table-column label="目标" min-width="140">
              <template #default="{ row }">{{ auditDetailText(row) }}</template>
            </el-table-column>
            <el-table-column label="审批" width="100">
              <template #default="{ row }">
                <el-tag
                  size="small"
                  :type="row.human_approved === 1 ? 'success' : 'info'"
                >
                  {{ APPROVAL_TEXT[row.human_approved] ?? '未知' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.agent-monitor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}

.agent-monitor__toolbar-inner {
  display: flex;
  align-items: center;
  gap: 12px;
}

.agent-monitor__title {
  margin-right: auto;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.agent-monitor__detail {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.agent-monitor__panel {
  flex: 1;
  min-width: 0;
}

.agent-monitor__panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.agent-monitor__stats {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.agent-monitor__stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  padding: 10px 12px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafafa;
}

.agent-monitor__stat-label {
  font-size: 12px;
  color: #909399;
}

.agent-monitor__stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.agent-monitor__messages {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 380px;
  overflow-y: auto;
}

.agent-monitor__message {
  padding: 8px 10px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fff;
}

.agent-monitor__message--assistant {
  background: #f0f9ff;
  border-color: #c6e2ff;
}

.agent-monitor__message--tool {
  background: #fafafa;
}

.agent-monitor__message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.agent-monitor__tool-name,
.agent-monitor__message-time {
  font-size: 12px;
  color: #909399;
}

.agent-monitor__message-body {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
}
</style>
