<template>
  <div class="execution-log-panel" style="margin-top: 20px">
    <el-collapse v-model="ctx.logActiveNames.value">
      <el-collapse-item name="logs">
        <template #title>
          <span class="collapse-title">
            <el-icon><Document /></el-icon>实时执行日志
            <el-tag
              size="small"
              :type="ctx.executionLogs.value.length > 0 ? 'primary' : 'info'"
              style="margin-left: 8px"
              >{{ ctx.executionLogs.value.length }} 条</el-tag
            >
          </span>
        </template>
        <div class="log-toolbar">
          <el-checkbox v-model="ctx.autoScroll.value">自动滚动</el-checkbox>
          <el-button size="small" :icon="Download" @click="ctx.exportLogs" :disabled="ctx.executionLogs.value.length === 0"
            >导出日志</el-button
          >
          <el-button size="small" :icon="Delete" @click="ctx.clearLogs" :disabled="ctx.executionLogs.value.length === 0"
            >清空</el-button
          >
        </div>
        <el-scrollbar ref="ctx.scrollbarRef" height="300px" always>
          <div ref="ctx.logContainerRef.value" class="log-container">
            <div
              v-for="(log, index) in ctx.executionLogs.value"
              :key="index"
              :class="['log-item', ctx.getLogItemClass(log.status)]"
            >
              <span class="log-time">{{ ctx.formatTime(log.timestamp) }}</span>
              <el-tag :type="ctx.logStatusColor(log.status)" size="small" effect="plain">{{
                ctx.logStatusText(log.status)
              }}</el-tag>
              <span v-if="log.case_no" class="log-case">[{{ log.case_no }}]</span>
              <span class="log-text">{{ log.log }}</span>
            </div>
            <el-empty v-if="ctx.executionLogs.value.length === 0" description="暂无执行日志" :image-size="60" />
          </div>
        </el-scrollbar>
      </el-collapse-item>
    </el-collapse>

    <!-- 日志查看弹窗 -->
    <el-dialog v-model="ctx.logDialogVisible.value" title="用例执行日志" width="70%">
      <pre class="case-log-content">{{ ctx.currentCaseLog.value }}</pre>
    </el-dialog>

    <!-- 截图查看弹窗 -->
    <el-dialog v-model="ctx.screenshotDialogVisible.value" title="执行截图" width="70%">
      <div class="screenshot-container">
        <img :src="ctx.currentScreenshot.value" alt="执行截图" class="screenshot-img" />
      </div>
    </el-dialog>

    <!-- 错误详情弹窗 -->
    <el-dialog v-model="ctx.errorDialogVisible.value" title="错误详情" width="70%">
      <pre class="error-content">{{ ctx.currentError.value }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Document, Download, Delete } from '@element-plus/icons-vue'
import { useTaskDetail } from '@/composables/task/useTaskDetail'

const ctx = useTaskDetail()
</script>

<style scoped>
.collapse-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
}
.log-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.log-container {
  padding: 8px 12px;
  background: var(--color-bg-page, #f5f7fa);
  border-radius: 6px;
  min-height: 300px;
}
.log-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
  font-family: 'Consolas', 'Monaco', monospace;
  border-bottom: 1px solid var(--color-border-light, #ebeef5);
}
.log-item:last-child {
  border-bottom: none;
}
.log-item.log-error {
  color: var(--color-danger, #f56c6c);
}
.log-item.log-warning {
  color: var(--color-warning, #e6a23c);
}
.log-item.log-success {
  color: var(--color-success, #67c23a);
}
.log-time {
  color: var(--color-info, #909399);
  white-space: nowrap;
  flex-shrink: 0;
}
.log-case {
  color: var(--color-primary, #409eff);
  font-weight: 600;
  white-space: nowrap;
}
.log-text {
  word-break: break-all;
}
.case-log-content,
.error-content {
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  max-height: 500px;
  overflow-y: auto;
  padding: 12px;
  background: var(--color-bg-page, #f5f7fa);
  border-radius: 6px;
}
.screenshot-container {
  text-align: center;
}
.screenshot-img {
  max-width: 100%;
  border-radius: 6px;
  border: 1px solid var(--color-border-light, #ebeef5);
}
</style>
