/**
 * 视频回放 Composable
 * 职责：视频播放控制、回放控制
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  startReplay as startReplayApi,
  pauseReplay as pauseReplayApi,
  stopReplay as stopReplayApi,
} from '@/api/testExecution'

export interface UseVideoReplayOptions {
  /** 当前任务ID */
  taskId: () => number
  /** 任务信息（用于构建executionId） */
  taskInfo: import('vue').Ref<Record<string, unknown> | null>
  /** 视频元素模板引用 */
  videoPlayer: import('vue').Ref<HTMLVideoElement | undefined>
}

export function useVideoReplay(options: UseVideoReplayOptions) {
  const isVideoPlaying = ref(false)
  const videoCurrentTime = ref(0)
  const videoDuration = ref(0)
  const replaySpeed = ref(1)

  /** 构建回放执行ID */
  const buildExecutionId = (): string => {
    const taskInfoVal = options.taskInfo.value
    const caseId = taskInfoVal
      ? ((taskInfoVal as Record<string, unknown>).case_id ??
        (taskInfoVal as Record<string, unknown>)?.task)
        ? ((taskInfoVal as Record<string, unknown>).task as Record<string, unknown>)?.case_id
        : undefined
      : undefined
    return `${options.taskId()}_${caseId ?? ''}`
  }

  const toggleVideoPlay = () => {
    if (options.videoPlayer.value) {
      if (isVideoPlaying.value) {
        options.videoPlayer.value.pause()
      } else {
        options.videoPlayer.value.play()
      }
      isVideoPlaying.value = !isVideoPlaying.value
    }
  }

  const seekVideo = (seconds: number) => {
    if (options.videoPlayer.value) {
      options.videoPlayer.value.currentTime += seconds
    }
  }

  const onVideoTimeChange = (value: number) => {
    if (options.videoPlayer.value) {
      options.videoPlayer.value.currentTime = value
    }
  }

  const startReplay = async () => {
    try {
      const executionId = buildExecutionId()
      await startReplayApi(executionId)
      ElMessage.success('开始回放')
    } catch (error) {
      console.error('开始回放失败:', error)
      ElMessage.error('开始回放失败')
    }
  }

  const pauseReplay = async () => {
    try {
      const executionId = buildExecutionId()
      await pauseReplayApi(executionId)
      ElMessage.success('已暂停回放')
    } catch (error) {
      console.error('暂停回放失败:', error)
    }
  }

  const stopReplay = async () => {
    try {
      const executionId = buildExecutionId()
      await stopReplayApi(executionId)
      ElMessage.success('已停止回放')
    } catch (error) {
      console.error('停止回放失败:', error)
    }
  }

  return {
    isVideoPlaying,
    videoCurrentTime,
    videoDuration,
    replaySpeed,
    toggleVideoPlay,
    seekVideo,
    onVideoTimeChange,
    startReplay,
    pauseReplay,
    stopReplay,
  }
}
