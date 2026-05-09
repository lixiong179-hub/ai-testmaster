<template>
  <el-dialog
    v-model="visible"
    title="智能识别页面跳转"
    width="640px"
    :close-on-click-modal="false"
    destroy-on-close
    @open="handleOpen"
  >
    <div v-if="suggestions.length === 0 && !analyzing" class="empty-state">
      <el-icon :size="40" color="#c0c4cc"><Connection /></el-icon>
      <p>未发现页面跳转关系</p>
      <p class="hint">确保页面存在 ui_spec_elements 数据（按钮、链接、文案等）</p>
    </div>
    <div v-if="analyzing" class="analyzing-state">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span>正在分析页面跳转关系...</span>
    </div>
    <div v-if="suggestions.length > 0 && !analyzing" class="suggestion-list">
      <div class="list-header">
        <span class="count">共 {{ suggestions.length }} 条建议连线</span>
        <div class="batch-actions">
          <el-button size="small" type="primary" text @click="acceptAll">全部接受</el-button>
          <el-button size="small" text @click="ignoreAll">全部忽略</el-button>
        </div>
      </div>
      <div
        v-for="(item, idx) in displaySuggestions"
        :key="idx"
        class="suggestion-item"
        :class="{ accepted: item.accepted, ignored: item.ignored }"
      >
        <div class="item-main">
          <div class="node-connection">
            <span class="source">{{ item.sourceScreenName }}</span>
            <el-icon class="arrow"><ArrowRight /></el-icon>
            <span class="target">{{ item.targetScreenName }}</span>
            <el-tag size="small" type="info" effect="plain" class="match-score">
              {{ item.matchScore }}%
            </el-tag>
          </div>
          <p class="reason">{{ item.reason }}</p>
        </div>
        <div class="item-actions" v-if="!item.ignored">
          <el-button
            v-if="!item.accepted"
            size="small"
            type="success"
            @click="item.accepted = true"
          >
            <el-icon><Check /></el-icon>接受
          </el-button>
          <el-button
            v-if="item.accepted"
            size="small"
            type="warning"
            @click="item.accepted = false"
          >
            <el-icon><RefreshRight /></el-icon>撤销
          </el-button>
          <el-button size="small" @click="item.ignored = true">
            <el-icon><Close /></el-icon>忽略
          </el-button>
        </div>
      </div>
    </div>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="visible = false">关闭</el-button>
        <el-button type="primary" :disabled="acceptedCount === 0" @click="handleConfirm">
          应用 {{ acceptedCount }} 条连线
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, nextTick } from 'vue'
import {
  Connection,
  Loading,
  ArrowRight,
  Check,
  Close,
  RefreshRight,
} from '@element-plus/icons-vue'
import { useEdgeSuggestion, type EdgeSuggestion } from '@/composables/useEdgeSuggestion'
import type { Edge } from '@vue-flow/core'
import type { FlowEditorNode } from '@/composables/useFlowEditor'

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  nodes: FlowEditorNode[]
  edges: Edge[]
}>()

const emit = defineEmits<{
  confirm: [accepted: EdgeSuggestion[]]
}>()

const { suggestions, runAnalysis, clearSuggestions } = useEdgeSuggestion()

interface DisplaySuggestion extends EdgeSuggestion {
  ignored: boolean
}

const displaySuggestions = ref<DisplaySuggestion[]>([])
const analyzing = ref(false)

const acceptedCount = computed(
  () => displaySuggestions.value.filter((s) => s.accepted && !s.ignored).length
)

const handleOpen = async () => {
  analyzing.value = true
  await nextTick()
  const raw = runAnalysis(props.nodes, props.edges)
  displaySuggestions.value = raw.map((s) => ({ ...s, ignored: false }))
  analyzing.value = false
}

const acceptAll = () => {
  displaySuggestions.value.forEach((s) => {
    if (!s.ignored) s.accepted = true
  })
}

const ignoreAll = () => {
  displaySuggestions.value.forEach((s) => {
    s.ignored = true
  })
}

const handleConfirm = () => {
  const accepted = displaySuggestions.value.filter((s) => s.accepted && !s.ignored)
  emit('confirm', accepted)
  visible.value = false
  clearSuggestions()
}
</script>

<style scoped lang="scss">
.empty-state {
  text-align: center;
  padding: 40px 0;
  color: #909399;

  p {
    margin-top: 12px;
  }

  .hint {
    font-size: 12px;
    color: #c0c4cc;
  }
}

.analyzing-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 0;
  color: #606266;
  font-size: 14px;
}

.suggestion-list {
  max-height: 420px;
  overflow-y: auto;

  .list-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 4px 12px;
    border-bottom: 1px solid #ebeef5;
    margin-bottom: 8px;

    .count {
      font-size: 13px;
      color: #606266;
    }
  }
}

.suggestion-item {
  padding: 10px 8px;
  border-radius: 6px;
  transition: background 0.2s;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;

  &:hover {
    background: #f5f7fa;
  }

  &.ignored {
    opacity: 0.45;
  }

  &.accepted {
    border-left: 3px solid #67c23a;
    background: rgba(103, 194, 58, 0.04);
  }

  .item-main {
    flex: 1;
    min-width: 0;

    .node-connection {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;

      .source {
        color: #409eff;
        font-weight: 500;
      }

      .target {
        color: #67c23a;
        font-weight: 500;
      }

      .arrow {
        color: #c0c4cc;
      }

      .match-score {
        margin-left: 4px;
      }
    }

    .reason {
      margin: 6px 0 0;
      font-size: 12px;
      color: #909399;
      word-break: break-all;
    }
  }

  .item-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
