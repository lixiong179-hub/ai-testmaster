<template>
  <div class="execution-results" style="margin-top: 20px">
    <el-collapse v-model="ctx.activeNames.value">
      <el-collapse-item title="执行结果" name="results">
        <template #title>
          <span class="collapse-title">
            <el-icon><List /></el-icon>执行结果
            <el-tag size="small" type="info" style="margin-left: 8px">{{ ctx.taskResults.value.length }} 条</el-tag>
          </span>
        </template>
        <el-table v-loading="ctx.loading.value" :data="ctx.taskResults.value" style="width: 100%" border stripe max-height="400">
          <el-table-column prop="case_no" label="用例编号" width="130" />
          <el-table-column prop="case_id" label="用例ID" width="80" align="center" />
          <el-table-column prop="exec_status" label="执行状态" width="120" align="center">
            <template #default="scope">
              <el-tag :type="ctx.execStatusColor(scope.row.exec_status)" effect="dark">{{ ctx.execStatusText(scope.row.exec_status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="exec_time" label="执行时长" width="120">
            <template #default="scope">{{ scope.row.exec_time || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="280" align="center">
            <template #default="scope">
              <el-space>
                <el-button type="info" size="small" link @click="ctx.viewCaseLog(scope.row)">查看日志</el-button>
                <el-button v-if="scope.row.screenshot_url" type="primary" size="small" link @click="ctx.viewScreenshot(scope.row)">查看截图</el-button>
                <el-button v-if="scope.row.error_msg" type="danger" size="small" link @click="ctx.viewError(scope.row)">查看错误</el-button>
              </el-space>
            </template>
          </el-table-column>
        </el-table>
      </el-collapse-item>
    </el-collapse>
  </div>

  <div class="execution-logs" style="margin-top: 20px">
    <el-collapse v-model="ctx.logActiveNames.value">
      <el-collapse-item title="执行日志" name="logs">
        <template #title>
          <span class="collapse-title">
            <el-icon><Document /></el-icon>执行日志
            <el-badge v-if="ctx.executionLogs.value.length > 0" :value="ctx.executionLogs.value.length" type="primary" style="margin-left: 8px" />
          </span>
        </template>
        <div class="log-toolbar">
          <el-button size="small" @click="ctx.clearLogs"><el-icon><Delete /></el-icon>清空日志</el-button>
          <el-button size="small" @click="ctx.exportLogs" :disabled="ctx.executionLogs.value.length === 0"><el-icon><Download /></el-icon>导出日志</el-button>
          <el-checkbox v-model="ctx.autoScroll.value" size="small" style="margin-left: 10px">自动滚动</el-checkbox>
        </div>
        <el-scrollbar style="height: 400px" ref="ctx.scrollbarRef.value">
          <div class="log-container" ref="ctx.logContainerRef.value">
            <div v-for="(item, index) in ctx.executionLogs.value" :key="index" :class="['log-item', ctx.getLogItemClass(item.status)]">
              <div class="log-header">
                <span class="log-time">{{ ctx.formatTime(item.timestamp) }}</span>
                <span class="log-case" v-if="item.case_no">[{{ item.case_no }}]</span>
                <el-tag :type="ctx.logStatusColor(item.status)" size="small">{{ ctx.logStatusText(item.status) }}</el-tag>
              </div>
              <div class="log-content">{{ item.log }}</div>
            </div>
            <div v-if="ctx.executionLogs.value.length === 0" class="empty-log">
              <el-empty description="暂无执行日志" :image-size="80" />
            </div>
          </div>
        </el-scrollbar>
      </el-collapse-item>
    </el-collapse>
  </div>

  <el-dialog v-model="ctx.logDialogVisible.value" title="用例执行日志" width="80%" top="5vh">
    <div class="case-log"><pre>{{ ctx.currentCaseLog.value }}</pre></div>
    <template #footer>
      <el-button @click="ctx.copyLog">复制日志</el-button>
      <el-button type="primary" @click="ctx.logDialogVisible.value = false">关闭</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="ctx.screenshotDialogVisible.value" title="失败截图" width="80%" top="5vh">
    <div class="screenshot-preview">
      <el-image v-if="ctx.currentScreenshot.value" :src="ctx.currentScreenshot.value" :preview-src-list="[ctx.currentScreenshot.value]" fit="contain" style="max-height: 70vh" />
      <div v-else class="no-screenshot"><el-empty description="暂无截图" /></div>
    </div>
  </el-dialog>

  <el-dialog v-model="ctx.errorDialogVisible.value" title="错误详情" width="60%" top="10vh">
    <div class="error-detail"><pre>{{ ctx.currentError.value }}</pre></div>
  </el-dialog>
</template>

<script setup lang="ts">
import { List, Document, Delete, Download } from '@element-plus/icons-vue'
import { useTaskDetail } from '@/composables/task/useTaskDetail'

const ctx = useTaskDetail()
</script>

<style scoped>
.collapse-title { display: flex; align-items: center; font-weight: 600; }
.log-toolbar { display: flex; align-items: center; margin-bottom: 10px; gap: 10px; }
.log-container { padding: 10px; font-family: 'Courier New', Courier, monospace; font-size: 13px; min-height: 350px; }
.log-item { margin-bottom: 8px; padding: 8px 12px; border-radius: 4px; background: #f5f7fa; border-left: 3px solid #909399; }
.log-item.log-success { background: #f0f9eb; border-left-color: #67c23a; }
.log-item.log-error { background: #fef0f0; border-left-color: #f56c6c; }
.log-item.log-warning { background: #fdf6ec; border-left-color: #e6a23c; }
.log-header { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; font-size: 12px; color: #909399; }
.log-time { font-weight: 500; }
.log-case { font-weight: 700; color: #409eff; }
.log-content { white-space: pre-wrap; word-break: break-all; line-height: 1.6; color: #303133; }
.empty-log { display: flex; justify-content: center; align-items: center; min-height: 300px; }
.case-log { max-height: 60vh; overflow-y: auto; background: #f5f7fa; padding: 15px; border-radius: 4px; }
.case-log pre { margin: 0; font-family: 'Courier New', Courier, monospace; font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-break: break-all; }
.screenshot-preview { text-align: center; background: #f5f7fa; padding: 20px; border-radius: 4px; }
.no-screenshot { padding: 40px 0; }
.error-detail { background: #fef0f0; padding: 15px; border-radius: 4px; border: 1px solid #fde2e2; }
.error-detail pre { margin: 0; font-family: 'Courier New', Courier, monospace; font-size: 13px; line-height: 1.6; color: #f56c6c; white-space: pre-wrap; word-break: break-all; }
</style>
