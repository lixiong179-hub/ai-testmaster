import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/execution/useTestExecution', () => ({
  useTestExecution: () => state.current,
}))

import ExecutionSidePanel from '../ExecutionSidePanel.vue'

const ElTabsStub = defineComponent({
  name: 'ElTabs',
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: '<div class="el-tabs"><slot /></div>',
})
const ElTabPaneStub = defineComponent({
  name: 'ElTabPane',
  props: { label: { type: String, default: '' }, name: { type: String, default: '' } },
  template:
    '<div class="el-tab-pane" :data-name="name"><span class="pane-label">{{ label }}</span><slot /></div>',
})
const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: `<div class="el-dialog" v-if="modelValue" :data-title="title">
    <div class="el-dialog__body"><slot /></div>
    <div class="el-dialog__footer"><slot name="footer" /></div>
  </div>`,
})

const stubs = { ElTabs: ElTabsStub, ElTabPane: ElTabPaneStub, ElDialog: ElDialogStub }

const actions = {
  seekVideo: vi.fn(),
  toggleVideoPlay: vi.fn(),
  onVideoTimeChange: vi.fn(),
  startReplay: vi.fn(),
  pauseReplay: vi.fn(),
  stopReplay: vi.fn(),
  loadConnectedDevices: vi.fn(),
  saveVisibilityConfig: vi.fn(),
}

function makeCtx(over: Record<string, unknown> = {}) {
  return {
    activeTab: ref('logs'),
    executionLogs: ref([
      { level: 'info', message: '开始执行', timestamp: '2026-11-16T08:00:00Z' },
      { level: 'error', message: '元素未找到', timestamp: '2026-11-16T08:00:05Z' },
    ]),
    formatLogTime: (time: string) => `时间:${time.slice(11, 19)}`,
    videoUrl: ref<string>('https://cdn.example.com/run.mp4'),
    isVideoPlaying: ref(false),
    videoCurrentTime: ref(0),
    videoDuration: ref(120),
    executionStatus: ref<{ status: string }>({ status: 'completed' }),
    replaySpeed: ref(1),
    showConfigDialog: ref(false),
    visibilityConfig: ref({ headless: true, recordVideo: false, videoFps: 15 }),
    videoResolution: ref('1920x1080'),
    useMcpMode: ref(false),
    executionMode: ref('smart'),
    mobileDeviceId: ref(''),
    loadingDevices: ref(false),
    connectedDevices: ref([
      { udid: 'device-1', model: 'Pixel', state: 'device' },
      { udid: 'device-2', model: 'Offline', state: 'offline' },
    ]),
    saveConfigLoading: ref(false),
    logsContainer: ref<HTMLElement | undefined>(undefined),
    videoPlayer: ref<HTMLVideoElement | undefined>(undefined),
    ...actions,
    ...over,
  }
}

let ctx: Record<string, unknown>

async function mountPanel(over: Record<string, unknown> = {}) {
  ctx = makeCtx(over)
  state.current = ctx
  const wrapper = mount(ExecutionSidePanel, { global: { stubs } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ExecutionSidePanel — 执行日志', () => {
  it('渲染日志级别、时间与消息', async () => {
    const wrapper = await mountPanel()

    const items = wrapper.findAll('.log-item')
    expect(items).toHaveLength(2)
    expect(items[0].classes()).toContain('info')
    expect(items[0].text()).toContain('[INFO]')
    expect(items[0].text()).toContain('时间:08:00:00')
    expect(items[1].classes()).toContain('error')
    expect(items[1].text()).toContain('元素未找到')
  })

  it('日志容器完成 ref 绑定', async () => {
    await mountPanel()

    expect((ctx.logsContainer as { value?: unknown }).value).toBeInstanceOf(HTMLElement)
  })
})

describe('ExecutionSidePanel — 执行视频', () => {
  it('有视频时渲染播放器与控制条', async () => {
    const wrapper = await mountPanel()

    expect(wrapper.find('.execution-video').attributes('src')).toBe(
      'https://cdn.example.com/run.mp4'
    )
    expect((ctx.videoPlayer as { value?: unknown }).value).toBeInstanceOf(HTMLVideoElement)
    expect(wrapper.text()).toContain('播放')
  })

  it('点击快退/播放/快进透传动作', async () => {
    const wrapper = await mountPanel()

    const buttons = wrapper.findAll('.video-controls .el-button')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    await buttons[2].trigger('click')

    expect(actions.seekVideo).toHaveBeenNthCalledWith(1, -10)
    expect(actions.toggleVideoPlay).toHaveBeenCalledTimes(1)
    expect(actions.seekVideo).toHaveBeenNthCalledWith(2, 10)
  })

  it('播放中展示暂停文案', async () => {
    const wrapper = await mountPanel({ isVideoPlaying: ref(true) })

    expect(wrapper.text()).toContain('暂停')
  })

  it('无视频时展示空态并可开启录制配置', async () => {
    const wrapper = await mountPanel({ videoUrl: ref('') })

    expect(wrapper.text()).toContain('视频录制未启用或执行未完成')
    const btn = wrapper.findAll('.el-button').find((n) => n.text() === '启用视频录制')!
    await btn.trigger('click')

    expect((ctx.showConfigDialog as { value: boolean }).value).toBe(true)
  })

  it('拖动进度条回写播放位置', async () => {
    const wrapper = await mountPanel()

    wrapper.findAllComponents({ name: 'ElSlider' })[0].vm.$emit('change', 30)

    expect(actions.onVideoTimeChange).toHaveBeenCalledWith(30)
  })
})

describe('ExecutionSidePanel — 回放控制', () => {
  it('执行完成时展示回放页签与控件', async () => {
    const wrapper = await mountPanel()

    expect(wrapper.find('.replay-controls').exists()).toBe(true)
    const buttons = wrapper.findAll('.replay-controls .el-button')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    await buttons[2].trigger('click')

    expect(actions.startReplay).toHaveBeenCalledTimes(1)
    expect(actions.pauseReplay).toHaveBeenCalledTimes(1)
    expect(actions.stopReplay).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('1x')
  })

  it('未完成时隐藏回放页签', async () => {
    const wrapper = await mountPanel({ executionStatus: ref({ status: 'running' }) })

    expect(wrapper.find('.replay-controls').exists()).toBe(false)
  })
})

describe('ExecutionSidePanel — 可见模式配置', () => {
  it('配置弹窗渲染基础开关与执行模式说明', async () => {
    const wrapper = await mountPanel({ showConfigDialog: ref(true) })

    expect(wrapper.find('.el-dialog').attributes('data-title')).toBe('可见模式配置')
    expect(wrapper.text()).toContain('优先使用缓存定位，失败后AI实时识别')
    // 未开启录制时不展示分辨率与帧率
    expect(wrapper.text()).not.toContain('视频分辨率')
  })

  it('开启录制后展示分辨率与帧率', async () => {
    const wrapper = await mountPanel({
      showConfigDialog: ref(true),
      visibilityConfig: ref({ headless: true, recordVideo: true, videoFps: 30 }),
    })

    expect(wrapper.text()).toContain('视频分辨率')
    expect(wrapper.text()).toContain('30 fps')
  })

  it('移动端模式展示设备选择与提示，并过滤离线设备', async () => {
    const wrapper = await mountPanel({
      showConfigDialog: ref(true),
      executionMode: ref('mobile_smart'),
    })

    expect(wrapper.text()).toContain('移动端：优先使用缓存定位，失败后AI实时识别（ADB）')
    expect(wrapper.text()).toContain('目标设备')
    expect(wrapper.text()).toContain('请确保设备已通过ADB连接')

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[selects.length - 1].vm.$emit('focus')
    expect(actions.loadConnectedDevices).toHaveBeenCalled()
  })

  it('保存与取消按钮分别保存配置、关闭弹窗', async () => {
    const wrapper = await mountPanel({ showConfigDialog: ref(true) })
    const footerButtons = wrapper.findAll('.el-dialog__footer .el-button')

    await footerButtons[0].trigger('click')
    expect((ctx.showConfigDialog as { value: boolean }).value).toBe(false)
    ;(ctx.showConfigDialog as { value: boolean }).value = true
    await flushPromises()
    const saveBtn = wrapper
      .findAll('.el-dialog__footer .el-button')
      .find((n) => n.text() === '保存配置')!
    await saveBtn.trigger('click')

    expect(actions.saveVisibilityConfig).toHaveBeenCalledTimes(1)
  })
})
