import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/task/useTaskDetail', () => ({
  useTaskDetail: () => state.current,
}))

import TaskResultsPanel from '../TaskResultsPanel.vue'

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: `<div class="el-dialog" v-if="modelValue" :data-title="title">
    <div class="el-dialog__body"><slot /></div>
    <div class="el-dialog__footer"><slot name="footer" /></div>
  </div>`,
})

const stubs = { ElDialog: ElDialogStub }

const actions = {
  viewCaseLog: vi.fn(),
  viewScreenshot: vi.fn(),
  viewError: vi.fn(),
  clearLogs: vi.fn(),
  exportLogs: vi.fn(),
  copyLog: vi.fn(),
}

function makeResult(over: Record<string, unknown> = {}) {
  return {
    case_no: 'CASE-001',
    case_id: 11,
    exec_status: 'success',
    exec_time: '3s',
    screenshot_url: null,
    error_msg: null,
    ...over,
  }
}

function makeCtx(over: Record<string, unknown> = {}) {
  return {
    activeNames: ref<string[]>((over.activeNames as string[] | undefined) ?? ['results']),
    logActiveNames: ref<string[]>((over.logActiveNames as string[] | undefined) ?? ['logs']),
    taskResults: ref([
      makeResult(),
      makeResult({
        case_no: 'CASE-002',
        case_id: 12,
        exec_status: 'failed',
        exec_time: null,
        screenshot_url: 'shot.png',
        error_msg: '断言失败',
      }),
    ]),
    loading: ref(false),
    executionLogs: ref([
      {
        case_no: 'CASE-001',
        status: 'success',
        timestamp: '2026-11-16T08:00:00Z',
        log: '启动浏览器',
      },
      { case_no: null, status: 'error', timestamp: '2026-11-16T08:00:10Z', log: '元素未找到' },
    ]),
    autoScroll: ref(true),
    scrollbarRef: ref<unknown>(null),
    logContainerRef: ref<HTMLElement | null>(null),
    logDialogVisible: ref(false),
    currentCaseLog: ref(''),
    screenshotDialogVisible: ref(false),
    currentScreenshot: ref(''),
    errorDialogVisible: ref(false),
    currentError: ref(''),
    execStatusText: (status: string) => (status === 'failed' ? '失败' : '通过'),
    execStatusColor: (status: string) => (status === 'failed' ? 'danger' : 'success'),
    getLogItemClass: (status: string) => `log-${status}`,
    formatTime: (time: string) => `时间:${time.slice(11, 19)}`,
    logStatusColor: (status: string) => (status === 'error' ? 'danger' : 'success'),
    logStatusText: (status: string) => (status === 'error' ? '异常' : '正常'),
    ...actions,
    ...over,
  }
}

let ctx: Record<string, unknown>

async function mountPanel(over: Record<string, unknown> = {}) {
  ctx = makeCtx(over)
  state.current = ctx
  const wrapper = mount(TaskResultsPanel, { global: { stubs } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('TaskResultsPanel — 执行结果', () => {
  it('渲染结果行与状态标签、耗时占位', async () => {
    const wrapper = await mountPanel()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('CASE-001')
    expect(rows[0].text()).toContain('通过')
    expect(rows[0].text()).toContain('3s')
    expect(rows[1].text()).toContain('失败')
    expect(rows[1].text()).toContain('-')
  })

  it('标题展示结果条数', async () => {
    const wrapper = await mountPanel()

    expect(wrapper.find('.collapse-title').text()).toContain('2 条')
  })

  it('按行渲染日志/截图/错误入口并透传行数据', async () => {
    const wrapper = await mountPanel()

    const rows = wrapper.findAll('.el-table__row')
    const firstButtons = rows[0].findAll('.el-button')
    expect(firstButtons.map((n) => n.text())).toEqual(['查看日志'])

    await firstButtons[0].trigger('click')
    expect(actions.viewCaseLog).toHaveBeenCalledWith(expect.objectContaining({ case_id: 11 }))

    const secondButtons = rows[1].findAll('.el-button')
    expect(secondButtons.map((n) => n.text())).toEqual(['查看日志', '查看截图', '查看错误'])

    await secondButtons[1].trigger('click')
    await secondButtons[2].trigger('click')
    expect(actions.viewScreenshot).toHaveBeenCalledWith(expect.objectContaining({ case_id: 12 }))
    expect(actions.viewError).toHaveBeenCalledWith(expect.objectContaining({ case_id: 12 }))
  })
})

describe('TaskResultsPanel — 执行日志', () => {
  it('日志数量徽标与日志条目样式', async () => {
    const wrapper = await mountPanel()

    expect(wrapper.find('.el-badge').exists()).toBe(true)

    const logs = wrapper.findAll('.log-item')
    expect(logs).toHaveLength(2)
    expect(logs[0].classes()).toContain('log-success')
    expect(logs[1].classes()).toContain('log-error')
    expect(logs[0].text()).toContain('[CASE-001]')
    expect(logs[0].text()).toContain('时间:08:00:00')
    expect(logs[1].text()).toContain('元素未找到')
    expect((ctx.logContainerRef as { value?: unknown }).value).toBeInstanceOf(HTMLElement)
  })

  it('清空与导出日志按钮透传动作', async () => {
    const wrapper = await mountPanel()

    const buttons = wrapper.findAll('.log-toolbar .el-button')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')

    expect(actions.clearLogs).toHaveBeenCalledTimes(1)
    expect(actions.exportLogs).toHaveBeenCalledTimes(1)
  })

  it('无日志时导出按钮禁用并展示空态', async () => {
    const wrapper = await mountPanel({ executionLogs: ref([]) })

    const exportBtn = wrapper.findAll('.log-toolbar .el-button')[1]
    expect(exportBtn.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('暂无执行日志')
    expect(wrapper.find('.el-badge').exists()).toBe(false)
  })

  it('自动滚动开关双向绑定', async () => {
    const wrapper = await mountPanel()

    const checkbox = wrapper.findComponent({ name: 'ElCheckbox' })
    await checkbox.vm.$emit('update:modelValue', false)

    expect((ctx.autoScroll as { value: boolean }).value).toBe(false)
  })
})

describe('TaskResultsPanel — 弹窗', () => {
  it('用例日志弹窗展示内容并支持复制', async () => {
    const wrapper = await mountPanel({
      logDialogVisible: ref(true),
      currentCaseLog: ref('日志正文'),
    })

    expect(wrapper.find('.el-dialog').attributes('data-title')).toBe('用例执行日志')
    expect(wrapper.find('.case-log').text()).toContain('日志正文')

    const copyBtn = wrapper
      .findAll('.el-dialog__footer .el-button')
      .find((n) => n.text() === '复制日志')!
    await copyBtn.trigger('click')

    expect(actions.copyLog).toHaveBeenCalledTimes(1)
  })

  it('截图弹窗无截图时展示空态', async () => {
    const wrapper = await mountPanel({ screenshotDialogVisible: ref(true) })

    expect(wrapper.text()).toContain('暂无截图')
  })

  it('截图弹窗有截图时渲染预览图', async () => {
    const wrapper = await mountPanel({
      screenshotDialogVisible: ref(true),
      currentScreenshot: ref('shot.png'),
    })

    const images = wrapper.findAllComponents({ name: 'ElImage' })
    expect(images[images.length - 1].props('src')).toBe('shot.png')
  })

  it('错误弹窗展示错误详情', async () => {
    const wrapper = await mountPanel({
      errorDialogVisible: ref(true),
      currentError: ref('断言失败：期望 1 实际 2'),
    })

    expect(wrapper.find('.error-detail').text()).toContain('期望 1 实际 2')
  })

  it('弹窗默认关闭时均不渲染', async () => {
    const wrapper = await mountPanel()

    expect(wrapper.find('.el-dialog').exists()).toBe(false)
  })
})
