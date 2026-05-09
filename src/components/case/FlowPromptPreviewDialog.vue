<template>
  <el-dialog
    v-model="visible"
    title="Graph Prompt 预览"
    width="780px"
    :close-on-click-modal="false"
    @open="handleOpen"
    @closed="handleClosed"
    class="flow-prompt-preview-dialog"
  >
    <div v-loading="loading" element-loading-text="正在构建 Prompt...">
      <template v-if="!loading && previewData">
        <div class="preview-stats">
          <div class="stat-item">
            <span class="stat-label">节点</span>
            <span class="stat-value">{{ previewData.node_count }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">连线</span>
            <span class="stat-value">{{ previewData.edge_count }}</span>
          </div>
          <div class="stat-item stat-main">
            <span class="stat-label">主干</span>
            <span class="stat-value">{{ previewData.main_count }}</span>
          </div>
          <div class="stat-item stat-branch">
            <span class="stat-label">分支</span>
            <span class="stat-value">{{ previewData.branch_count }}</span>
          </div>
          <div class="stat-item stat-exception">
            <span class="stat-label">异常</span>
            <span class="stat-value">{{ previewData.exception_count }}</span>
          </div>
          <div class="stat-item stat-bypass">
            <span class="stat-label">旁路</span>
            <span class="stat-value">{{ previewData.bypass_count }}</span>
          </div>
        </div>

        <div v-if="previewData.errors.length > 0" class="preview-issues preview-issues--error">
          <el-icon class="issues-icon"><WarningFilled /></el-icon>
          <span>结构错误（{{ previewData.errors.length }}）：</span>
          <ul>
            <li v-for="(err, i) in previewData.errors" :key="'err' + i">{{ err.msg }}</li>
          </ul>
        </div>

        <div v-if="previewData.warnings.length > 0" class="preview-issues preview-issues--warning">
          <el-icon class="issues-icon"><Warning /></el-icon>
          <span>建议优化（{{ previewData.warnings.length }}）：</span>
          <ul>
            <li v-for="(warn, i) in previewData.warnings" :key="'warn' + i">{{ warn.msg }}</li>
          </ul>
        </div>

        <div class="prompt-header">
          <span class="prompt-header-title">完整 Prompt 文本</span>
          <el-button size="small" text type="primary" @click="copyPrompt">
            <el-icon><CopyDocument /></el-icon>
            复制
          </el-button>
        </div>
        <pre class="prompt-content"><code>{{ previewData.graph_prompt }}</code></pre>
      </template>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Warning, WarningFilled, CopyDocument } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

interface PreviewResult {
  graph_prompt: string
  node_count: number
  edge_count: number
  main_count: number
  branch_count: number
  exception_count: number
  bypass_count: number
  errors: { msg: string }[]
  warnings: { msg: string }[]
}

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  flowSortData: Record<string, unknown>
  context?: Record<string, unknown>
}>()

const loading = ref(false)
const previewData = ref<PreviewResult | null>(null)

const handleOpen = async () => {
  await fetchPreview()
}

const handleClosed = () => {
  previewData.value = null
}

type PreviewApiResponse = {
  data: {
    code: number
    data: PreviewResult
    msg: string
  }
}

const fetchPreview = async () => {
  loading.value = true
  try {
    const response = (await request.post('/api/v1/testCase/preview-graph-prompt', {
      flow_sort_data: props.flowSortData,
      context: props.context || {},
    })) as PreviewApiResponse
    previewData.value = response.data.data
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '预览失败'
    ElMessage.error(msg)
    visible.value = false
  } finally {
    loading.value = false
  }
}

const copyPrompt = async () => {
  if (!previewData.value) return
  try {
    await navigator.clipboard.writeText(previewData.value.graph_prompt)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}
</script>

<style scoped lang="scss">
.flow-prompt-preview-dialog {
  .preview-stats {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;

    .stat-item {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 6px 14px;
      background: #f2f3f5;
      border-radius: 6px;
      font-size: 13px;

      .stat-label {
        color: #909399;
      }

      .stat-value {
        font-weight: 700;
        color: #303133;
      }

      &.stat-main .stat-value {
        color: #409eff;
      }
      &.stat-branch .stat-value {
        color: #67c23a;
      }
      &.stat-exception .stat-value {
        color: #f56c6c;
      }
      &.stat-bypass .stat-value {
        color: #e6a23c;
      }
    }
  }

  .preview-issues {
    padding: 10px 14px;
    border-radius: 6px;
    margin-bottom: 12px;
    font-size: 13px;

    .issues-icon {
      margin-right: 6px;
      vertical-align: middle;
    }

    ul {
      margin: 6px 0 0 20px;
      padding: 0;

      li {
        line-height: 1.7;
        color: #606266;
      }
    }

    &--error {
      background: #fef0f0;
      border: 1px solid #fbc4c4;
      color: #f56c6c;
    }

    &--warning {
      background: #fdf6ec;
      border: 1px solid #f5dab1;
      color: #e6a23c;
    }
  }

  .prompt-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;

    &-title {
      font-size: 14px;
      font-weight: 600;
      color: #303133;
    }
  }

  .prompt-content {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 16px;
    border-radius: 8px;
    font-size: 12px;
    line-height: 1.6;
    max-height: 420px;
    overflow: auto;
    white-space: pre-wrap;
    word-break: break-word;

    code {
      background: transparent;
      padding: 0;
      font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    }
  }
}
</style>
