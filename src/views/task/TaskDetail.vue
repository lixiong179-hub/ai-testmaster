<template>
  <div class="task-detail">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="title">任务详情</span>
          <div class="header-actions">
            <el-button @click="ctx.refreshAll" :loading="ctx.loading.value"
              ><el-icon><Refresh /></el-icon>刷新</el-button
            >
            <el-button @click="$router.back()">返回列表</el-button>
          </div>
        </div>
      </template>

      <div class="task-info" v-if="ctx.taskDetail.value">
        <el-row :gutter="20">
          <el-col :span="8"
            ><div class="info-item">
              <label>任务名称：</label><span>{{ ctx.taskDetail.value.task_name }}</span>
            </div></el-col
          >
          <el-col :span="8"
            ><div class="info-item">
              <label>任务状态：</label
              ><el-tag
                :type="ctx.taskStatusColor(ctx.taskDetail.value.status)"
                effect="dark"
                size="large"
                >{{ ctx.taskStatusText(ctx.taskDetail.value.status) }}</el-tag
              >
            </div></el-col
          >
          <el-col :span="8"
            ><div class="info-item">
              <label>创建时间：</label
              ><span>{{ ctx.formatTime(ctx.taskDetail.value.create_time) }}</span>
            </div></el-col
          >
        </el-row>
        <el-row :gutter="20" style="margin-top: 15px">
          <el-col :span="8"
            ><div class="info-item">
              <label>开始时间：</label
              ><span>{{
                ctx.taskDetail.value.start_time
                  ? ctx.formatTime(ctx.taskDetail.value.start_time)
                  : '-'
              }}</span>
            </div></el-col
          >
          <el-col :span="8"
            ><div class="info-item">
              <label>结束时间：</label
              ><span>{{
                ctx.taskDetail.value.end_time ? ctx.formatTime(ctx.taskDetail.value.end_time) : '-'
              }}</span>
            </div></el-col
          >
          <el-col :span="8"
            ><div class="info-item">
              <label>执行用户：</label><span>{{ ctx.taskDetail.value.executor_id || '-' }}</span>
            </div></el-col
          >
        </el-row>
      </div>

      <div v-if="!ctx.taskDetail.value && !ctx.loading.value" class="empty-state">
        <el-empty description="未找到任务信息" />
      </div>

      <div class="execution-progress" style="margin-top: 20px" v-if="ctx.taskDetail.value">
        <div class="progress-header">
          <span class="progress-label">执行进度</span>
          <span class="progress-time" v-if="ctx.taskDetail.value.status === 1"
            ><el-icon class="is-loading"><Loading /></el-icon>执行中...</span
          >
        </div>
        <el-progress
          :percentage="ctx.taskDetail.value.progress || 0"
          :stroke-width="20"
          :color="ctx.getProgressColor(ctx.taskDetail.value.progress)"
          :status="ctx.getProgressStatus()"
          :striped="ctx.taskDetail.value.status === 1"
          :striped-flow="ctx.taskDetail.value.status === 1"
        />
        <div class="progress-stats">
          <div class="stat-item">
            <span class="stat-value">{{ ctx.taskDetail.value.total_count || 0 }}</span
            ><span class="stat-label">总用例</span>
          </div>
          <div class="stat-item success">
            <span class="stat-value">{{ ctx.taskDetail.value.success_count || 0 }}</span
            ><span class="stat-label">成功</span>
          </div>
          <div class="stat-item danger">
            <span class="stat-value">{{ ctx.taskDetail.value.fail_count || 0 }}</span
            ><span class="stat-label">失败</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ ctx.taskPassRate.value }}%</span
            ><span class="stat-label">通过率</span>
          </div>
        </div>
      </div>

      <div class="action-buttons" style="margin-top: 20px" v-if="ctx.taskDetail.value">
        <el-space>
          <el-button
            v-if="ctx.taskDetail.value.status === 0"
            type="success"
            @click="ctx.startTask"
            :loading="ctx.actionLoading.value"
            ><el-icon><VideoPlay /></el-icon>启动任务</el-button
          >
          <el-button
            v-if="ctx.taskDetail.value.status === 1"
            type="warning"
            @click="ctx.stopTask"
            :loading="ctx.actionLoading.value"
            ><el-icon><VideoPause /></el-icon>停止任务</el-button
          >
          <el-button @click="ctx.fetchTaskResults" :loading="ctx.loading.value"
            ><el-icon><Refresh /></el-icon>刷新结果</el-button
          >
          <el-button @click="ctx.exportResults" :disabled="ctx.taskResults.value.length === 0"
            ><el-icon><Download /></el-icon>导出结果</el-button
          >
        </el-space>
        <div class="execution-mode-selector" v-if="ctx.taskDetail.value.status === 0">
          <span class="mode-label">执行模式：</span>
          <el-radio-group v-model="ctx.executionMode.value" size="small">
            <el-radio value="smart">智能模式（推荐）</el-radio>
            <el-radio value="realtime">实时识别模式</el-radio>
            <el-radio value="preprocess">预处理模式</el-radio>
            <el-radio value="mobile_smart">移动端智能模式</el-radio>
            <el-radio value="mobile_realtime">移动端实时模式</el-radio>
          </el-radio-group>
          <div class="mode-desc">
            <template v-if="ctx.executionMode.value === 'smart'"
              >优先使用缓存定位，失败后AI实时识别</template
            >
            <template v-else-if="ctx.executionMode.value === 'realtime'"
              >直接执行，无需预先补充元素定位</template
            >
            <template v-else-if="ctx.executionMode.value === 'preprocess'"
              >需要先批量补充元素定位信息才能执行</template
            >
            <template v-else-if="ctx.executionMode.value === 'mobile_smart'"
              >移动端：优先缓存定位+AI兜底（ADB）</template
            >
            <template v-else-if="ctx.executionMode.value === 'mobile_realtime'"
              >移动端：AI实时识别（ADB）</template
            >
          </div>
          <div
            v-if="ctx.executionMode.value.startsWith('mobile_')"
            class="mobile-device-selector"
            style="margin-top: 8px"
          >
            <span class="mode-label">目标设备：</span>
            <el-select
              v-model="ctx.mobileDeviceId.value"
              placeholder="选择已连接的设备"
              :loading="ctx.loadingDevices.value"
              @focus="ctx.loadConnectedDevices"
              size="small"
              style="width: 260px"
            >
              <el-option
                v-for="device in ctx.connectedDevices.value.filter((d) => d.state === 'device')"
                :key="device.udid"
                :label="`${device.model || device.udid} (${device.udid})`"
                :value="device.udid"
              />
            </el-select>
            <el-alert type="warning" :closable="false" style="margin-top: 8px; font-size: 12px"
              >请确保设备已通过ADB连接，且已开启USB调试模式</el-alert
            >
          </div>
        </div>
      </div>

      <TaskResultsPanel />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { Refresh, VideoPlay, VideoPause, Download, Loading } from '@element-plus/icons-vue'
import { provideTaskDetail } from '@/composables/task/useTaskDetail'
import TaskResultsPanel from './components/TaskResultsPanel.vue'

const ctx = provideTaskDetail()

onMounted(ctx.init)
onUnmounted(ctx.cleanup)
</script>

<style scoped>
.task-detail {
  padding: 20px;
  height: 100%;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header .title {
  font-size: 18px;
  font-weight: 600;
}
.header-actions {
  display: flex;
  gap: 10px;
}
.task-info {
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ef 100%);
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #e4e8ef;
}
.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.info-item label {
  font-weight: 600;
  color: #606266;
  min-width: 80px;
}
.info-item span {
  color: #303133;
}
.empty-state {
  padding: 60px 0;
}
.execution-progress {
  background: #fff;
  padding: 15px;
  border-radius: 8px;
  border: 1px solid #e4e8ef;
}
.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.progress-label {
  font-weight: 600;
  color: #303133;
}
.progress-time {
  color: #409eff;
  display: flex;
  align-items: center;
  gap: 5px;
}
.progress-stats {
  display: flex;
  justify-content: space-around;
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #ebeef5;
}
.stat-item {
  text-align: center;
  padding: 10px 20px;
  border-radius: 8px;
  background: #f5f7fa;
}
.stat-item.success {
  background: #f0f9eb;
}
.stat-item.danger {
  background: #fef0f0;
}
.stat-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: #303133;
}
.stat-item.success .stat-value {
  color: #67c23a;
}
.stat-item.danger .stat-value {
  color: #f56c6c;
}
.stat-label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}
.action-buttons {
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  gap: 12px;
}
.execution-mode-selector {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 16px;
  background: #f5f7fa;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}
.mode-label {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
  line-height: 24px;
  white-space: nowrap;
}
.mode-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  padding-left: 72px;
}
</style>
