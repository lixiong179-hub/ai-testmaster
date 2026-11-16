import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

vi.mock('@/api/testExecution', () => ({
  startReplay: vi.fn(),
  pauseReplay: vi.fn(),
  stopReplay: vi.fn(),
}))

import {
  startReplay as startReplayApi,
  pauseReplay as pauseReplayApi,
  stopReplay as stopReplayApi,
} from '@/api/testExecution'
import { useVideoReplay } from '../useVideoReplay'
import { silenceConsole, silenceElMessage } from '@/test-utils'

const startMock = vi.mocked(startReplayApi)
const pauseMock = vi.mocked(pauseReplayApi)
const stopMock = vi.mocked(stopReplayApi)

function fakeVideo() {
  const el = {
    currentTime: 0,
    play: vi.fn(),
    pause: vi.fn(),
  }
  return el
}

function setup(taskInfo: Record<string, unknown> | null = { case_id: 7 }, withVideo = true) {
  const video = fakeVideo()
  const videoPlayer = ref<HTMLVideoElement | undefined>(
    withVideo ? (video as unknown as HTMLVideoElement) : undefined
  )
  const api = useVideoReplay({
    taskId: () => 42,
    taskInfo: ref(taskInfo),
    videoPlayer,
  })
  return { api, video, videoPlayer }
}

describe('useVideoReplay — 播放控制', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('无视频元素时切换播放不做任何事', () => {
    const { api } = setup(null, false)

    api.toggleVideoPlay()

    expect(api.isVideoPlaying.value).toBe(false)
  })

  it('切换播放：首次 play，再次 pause', () => {
    const { api, video } = setup()

    api.toggleVideoPlay()
    expect(video.play).toHaveBeenCalledTimes(1)
    expect(api.isVideoPlaying.value).toBe(true)

    api.toggleVideoPlay()
    expect(video.pause).toHaveBeenCalledTimes(1)
    expect(api.isVideoPlaying.value).toBe(false)
  })

  it('seekVideo 相对偏移，onVideoTimeChange 绝对定位', () => {
    const { api, video } = setup()

    api.seekVideo(5)
    expect(video.currentTime).toBe(5)

    api.seekVideo(-2)
    expect(video.currentTime).toBe(3)

    api.onVideoTimeChange(30)
    expect(video.currentTime).toBe(30)
  })

  it('无视频元素时 seek 不报错', () => {
    const { api } = setup(null, false)

    expect(() => api.seekVideo(5)).not.toThrow()
    expect(() => api.onVideoTimeChange(5)).not.toThrow()
  })
})

describe('useVideoReplay — 回放接口', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    startMock.mockResolvedValue(undefined as never)
    pauseMock.mockResolvedValue(undefined as never)
    stopMock.mockResolvedValue(undefined as never)
    silenceElMessage('success')
    silenceElMessage('error')
    silenceConsole('error')
  })

  it('executionId 由 taskId 与 taskInfo.case_id 拼接', async () => {
    const { api } = setup({ case_id: 7 })

    await api.startReplay()

    expect(startMock).toHaveBeenCalledWith('42_7')
    expect(ElMessage.success).toHaveBeenCalledWith('开始回放')
  })

  it('taskInfo 缺 case_id 时回退 task.case_id', async () => {
    const { api } = setup({ task: { case_id: 9 } })

    await api.pauseReplay()

    expect(pauseMock).toHaveBeenCalledWith('42_9')
  })

  it('taskInfo 为空时 executionId 尾部留空', async () => {
    const { api } = setup(null)

    await api.stopReplay()

    expect(stopMock).toHaveBeenCalledWith('42_')
    expect(ElMessage.success).toHaveBeenCalledWith('已停止回放')
  })

  it('开始回放失败提示错误', async () => {
    startMock.mockRejectedValue(new Error('boom'))
    const { api } = setup()

    await api.startReplay()

    expect(ElMessage.error).toHaveBeenCalledWith('开始回放失败')
  })

  it('暂停失败仅记录日志，不提示成功', async () => {
    pauseMock.mockRejectedValue(new Error('boom'))
    const { api } = setup()

    await api.pauseReplay()

    expect(console.error).toHaveBeenCalled()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('停止失败仅记录日志', async () => {
    stopMock.mockRejectedValue(new Error('boom'))
    const { api } = setup()

    await api.stopReplay()

    expect(console.error).toHaveBeenCalled()
  })
})
