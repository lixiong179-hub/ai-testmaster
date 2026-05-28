<template>
  <div class="side-panel">
    <el-tabs v-model="ctx.activeTab.value">
      <el-tab-pane label="执行日志" name="logs">
        <div class="logs-container" :ref="setLogsContainerRef">
          <div
            v-for="(log, index) in ctx.executionLogs.value"
            :key="index"
            class="log-item"
            :class="log.level"
          >
            <span class="log-time">{{ ctx.formatLogTime(log.timestamp) }}</span>
            <span class="log-level">[{{ log.level.toUpperCase() }}]</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="执行视频" name="video">
        <div class="video-container">
          <video
            v-if="ctx.videoUrl.value"
            :src="ctx.videoUrl.value"
            controls
            class="execution-video"
            :ref="setVideoPlayerRef"
          ></video>
          <el-empty v-else description="暂无视频">
            <template #description>
              <p>视频录制未启用或执行未完成</p>
              <el-button type="primary" @click="ctx.showConfigDialog.value = true"
                >启用视频录制</el-button
              >
            </template>
          </el-empty>
        </div>
        <div class="video-controls" v-if="ctx.videoUrl.value">
          <el-button-group>
            <el-button @click="ctx.seekVideo(-10)"
              ><el-icon><ArrowLeft /></el-icon> -10s</el-button
            >
            <el-button @click="ctx.toggleVideoPlay">
              <el-icon><VideoPlay v-if="!ctx.isVideoPlaying.value" /><VideoPause v-else /></el-icon>
              {{ ctx.isVideoPlaying.value ? '暂停' : '播放' }}
            </el-button>
            <el-button @click="ctx.seekVideo(10)"
              >+10s <el-icon><ArrowRight /></el-icon
            ></el-button>
          </el-button-group>
          <el-slider
            v-model="ctx.videoCurrentTime.value"
            :max="ctx.videoDuration.value"
            @change="
              (val: number | number[]) => ctx.onVideoTimeChange(Array.isArray(val) ? val[0] : val)
            "
            class="video-progress"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane
        label="回放控制"
        name="replay"
        v-if="ctx.executionStatus.value?.status === 'completed'"
      >
        <div class="replay-controls">
          <el-button-group>
            <el-button @click="ctx.startReplay" type="primary"
              ><el-icon><VideoPlay /></el-icon>开始回放</el-button
            >
            <el-button @click="ctx.pauseReplay"
              ><el-icon><VideoPause /></el-icon>暂停</el-button
            >
            <el-button @click="ctx.stopReplay"
              ><el-icon><CircleClose /></el-icon>停止</el-button
            >
          </el-button-group>
          <div class="replay-speed">
            <span>回放速度:</span>
            <el-slider v-model="ctx.replaySpeed.value" :min="0.5" :max="2" :step="0.5" show-stops />
            <span>{{ ctx.replaySpeed.value }}x</span>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>

  <el-dialog v-model="ctx.showConfigDialog.value" title="可见模式配置" width="600px">
    <el-form :model="ctx.visibilityConfig.value" label-width="150px">
      <el-form-item label="无头模式">
        <el-switch
          v-model="ctx.visibilityConfig.value.headless"
          active-text="启用"
          inactive-text="禁用"
        />
        <div class="form-tip">禁用后浏览器窗口可见</div>
      </el-form-item>
      <el-form-item label="视频录制">
        <el-switch
          v-model="ctx.visibilityConfig.value.recordVideo"
          active-text="启用"
          inactive-text="禁用"
        />
        <div class="form-tip">启用后自动录制执行过程</div>
      </el-form-item>
      <el-form-item label="视频分辨率" v-if="ctx.visibilityConfig.value.recordVideo">
        <el-select v-model="ctx.videoResolution.value" placeholder="选择分辨率">
          <el-option label="1920x1080 (1080p)" value="1920x1080" />
          <el-option label="1280x720 (720p)" value="1280x720" />
          <el-option label="854x480 (480p)" value="854x480" />
        </el-select>
      </el-form-item>
      <el-form-item label="视频帧率" v-if="ctx.visibilityConfig.value.recordVideo">
        <el-slider
          v-model="ctx.visibilityConfig.value.videoFps"
          :min="15"
          :max="60"
          :step="15"
          show-stops
        />
        <span>{{ ctx.visibilityConfig.value.videoFps }} fps</span>
      </el-form-item>
      <el-form-item label="MCP定位引擎">
        <el-switch v-model="ctx.useMcpMode.value" active-text="MCP" inactive-text="VLM" />
        <div style="margin-top: 4px; font-size: 12px; color: #909399">
          启用Playwright MCP定位引擎，支持更精准的元素识别和自愈
        </div>
      </el-form-item>
      <el-form-item label="执行模式">
        <el-radio-group v-model="ctx.executionMode.value">
          <el-radio value="smart">智能模式（推荐）</el-radio>
          <el-radio value="realtime">实时识别模式</el-radio>
          <el-radio value="preprocess">预处理模式</el-radio>
          <el-radio value="mobile_smart">移动端智能模式</el-radio>
          <el-radio value="mobile_realtime">移动端实时模式</el-radio>
        </el-radio-group>
        <div style="margin-top: 4px; font-size: 12px; color: #909399">
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
            >移动端：优先使用缓存定位，失败后AI实时识别（ADB）</template
          >
          <template v-else-if="ctx.executionMode.value === 'mobile_realtime'"
            >移动端：直接执行，AI实时识别元素（ADB）</template
          >
        </div>
      </el-form-item>
      <el-form-item label="目标设备" v-if="ctx.executionMode.value.startsWith('mobile_')">
        <el-select
          v-model="ctx.mobileDeviceId.value"
          placeholder="选择已连接的设备"
          :loading="ctx.loadingDevices.value"
          @focus="ctx.loadConnectedDevices"
          style="width: 100%"
        >
          <el-option
            v-for="device in ctx.connectedDevices.value.filter((d) => d.state === 'device')"
            :key="device.udid"
            :label="`${device.model || device.udid} (${device.udid})`"
            :value="device.udid"
          />
        </el-select>
        <el-alert type="warning" :closable="false" style="margin-top: 8px"
          >请确保设备已通过ADB连接，且已开启USB调试模式</el-alert
        >
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="ctx.showConfigDialog.value = false">取消</el-button>
      <el-button
        type="primary"
        @click="ctx.saveVisibilityConfig"
        :loading="ctx.saveConfigLoading.value"
        >保存配置</el-button
      >
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ArrowLeft, ArrowRight, VideoPlay, VideoPause, CircleClose } from '@element-plus/icons-vue'
import { useTestExecution } from '@/composables/execution/useTestExecution'

const ctx = useTestExecution()

const setLogsContainerRef = (el: unknown) => {
  ctx.logsContainer.value = el instanceof HTMLElement ? el : undefined
}

const setVideoPlayerRef = (el: unknown) => {
  ctx.videoPlayer.value = el instanceof HTMLVideoElement ? el : undefined
}
</script>

<style scoped>
.side-panel {
  width: 300px;
  flex-shrink: 0;
  border-left: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.logs-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}
.log-item {
  padding: 4px 8px;
  margin-bottom: 2px;
  border-radius: 3px;
}
.log-item.info {
  color: #606266;
}
.log-item.warning {
  background: #fdf6ec;
  color: #e6a23c;
}
.log-item.error {
  background: #fef0f0;
  color: #f56c6c;
}
.log-time {
  color: #909399;
  margin-right: 8px;
}
.log-level {
  font-weight: 600;
  margin-right: 8px;
}
.log-message {
  white-space: pre-wrap;
  word-break: break-all;
}
.video-container {
  padding: 8px;
  text-align: center;
}
.execution-video {
  width: 100%;
  max-height: 200px;
}
.video-controls {
  padding: 8px;
}
.video-progress {
  margin-top: 8px;
}
.replay-controls {
  padding: 16px;
}
.replay-speed {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.replay-speed .el-slider {
  flex: 1;
}
.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>
