import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, nextTick, type Ref } from 'vue'
import type { BatchTask } from '@/api/batchLocator'

interface LocatorResult {
  case_id: number
  case_title: string
  status: string
  locator?: string
  error_message?: string
}

interface LocatorState {
  visible: Ref<boolean>
  loading: Ref<boolean>
  currentView: Ref<'config' | 'progress' | 'report'>
  selectedCaseIds: Ref<number[]>
  locatorType: Ref<'css' | 'xpath'>
  aiAssist: Ref<boolean>
  progress: Ref<number>
  progressMessage: Ref<string>
  results: Ref<LocatorResult[]>
  error: Ref<string>
  successCount: Ref<number>
  failCount: Ref<number>
  totalProcessed: Ref<number>
  hasResults: Ref<boolean>
  batchTasks: Ref<BatchTask[]>
}

const mocks = vi.hoisted(() => ({
  open: vi.fn(),
  close: vi.fn(),
  startLocate: vi.fn(),
  retryFailed: vi.fn(),
  applyResults: vi.fn(),
  cancelTask: vi.fn(),
  loadBatchTasks: vi.fn(),
  state: {} as unknown as LocatorState,
}))

// 组合式函数已有独立的 useBatchLocator.spec.ts 覆盖，这里只验证弹窗的模板与事件接线
vi.mock('../useBatchLocator', async () => {
  const { ref } = await import('vue')
  const s = mocks.state
  s.visible = ref(false)
  s.loading = ref(false)
  s.currentView = ref<'config' | 'progress' | 'report'>('config')
  s.selectedCaseIds = ref<number[]>([])
  s.locatorType = ref<'css' | 'xpath'>('css')
  s.aiAssist = ref(true)
  s.progress = ref(0)
  s.progressMessage = ref('')
  s.results = ref<LocatorResult[]>([])
  s.error = ref('')
  s.successCount = ref(0)
  s.failCount = ref(0)
  s.totalProcessed = ref(0)
  s.hasResults = ref(false)
  s.batchTasks = ref<BatchTask[]>([])
  return {
    useBatchLocator: () => ({
      visible: s.visible,
      loading: s.loading,
      currentView: s.currentView,
      selectedCaseIds: s.selectedCaseIds,
      locatorType: s.locatorType,
      aiAssist: s.aiAssist,
      progress: s.progress,
      progressMessage: s.progressMessage,
      results: s.results,
      error: s.error,
      successCount: s.successCount,
      failCount: s.failCount,
      totalProcessed: s.totalProcessed,
      hasResults: s.hasResults,
      batchTasks: s.batchTasks,
      open: mocks.open,
      close: mocks.close,
      startLocate: mocks.startLocate,
      retryFailed: mocks.retryFailed,
      applyResults: mocks.applyResults,
      cancelTask: mocks.cancelTask,
      loadBatchTasks: mocks.loadBatchTasks,
    }),
  }
})

import BatchLocatorDialog from '../BatchLocatorDialog.vue'

const state = mocks.state

/**
 * el-dialog 默认把内容 teleport 到 body，测试里拿不到内部节点；
 * 用轻量桩替换，仅保留「可见即渲染 + 默认插槽 + footer 插槽」的行为。
 */
const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: {
    modelValue: { type: Boolean, default: false },
    title: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'close'],
  template: `
    <div v-if="modelValue" class="el-dialog">
      <div class="el-dialog__header">{{ title }}</div>
      <slot />
      <div class="el-dialog__footer"><slot name="footer" /></div>
    </div>
  `,
})

function mountDialog() {
  return mount(BatchLocatorDialog, {
    props: { projectId: 7 },
    global: { stubs: { ElDialog: ElDialogStub } },
  })
}

function footerButtons(wrapper: ReturnType<typeof mount>): string[] {
  return wrapper.findAll('.dialog-footer button').map((btn) => btn.text())
}

function findFooterButton(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper.findAll('.dialog-footer button').find((btn) => btn.text().includes(text))
}

beforeEach(() => {
  vi.clearAllMocks()
  state.visible.value = false
  state.loading.value = false
  state.currentView.value = 'config'
  state.selectedCaseIds.value = []
  state.locatorType.value = 'css'
  state.aiAssist.value = true
  state.progress.value = 0
  state.progressMessage.value = ''
  state.results.value = []
  state.error.value = ''
  state.successCount.value = 0
  state.failCount.value = 0
  state.totalProcessed.value = 0
  state.hasResults.value = false
  state.batchTasks.value = []
})

describe('BatchLocatorDialog — 打开与历史任务', () => {
  it('exposed.open 打开弹窗并刷新历史任务列表', async () => {
    const wrapper = mountDialog()

    await (wrapper.vm as unknown as { open: (ids: number[]) => void }).open([3, 4])

    expect(mocks.open).toHaveBeenCalledWith([3, 4])
    expect(mocks.loadBatchTasks).toHaveBeenCalledTimes(1)
  })

  it('配置视图展示已选用例数量', async () => {
    state.selectedCaseIds.value = [1, 2, 3]
    state.visible.value = true
    const wrapper = mountDialog()
    await flushPromises()

    expect(wrapper.find('.config-section').text()).toContain('已选择 3 个用例进行批量元素定位')
  })

  it('无历史任务时不渲染历史表格', async () => {
    state.visible.value = true
    const wrapper = mountDialog()
    await flushPromises()

    expect(wrapper.find('.history-section').exists()).toBe(false)
  })

  it('有历史任务时渲染用例、状态与进度（缺失步数回退 0/0）', async () => {
    state.visible.value = true
    state.batchTasks.value = [
      {
        id: 1,
        case_title: '用例甲',
        status: 'completed',
        completed_steps: 3,
        total_steps: 4,
      } as unknown as BatchTask,
      { id: 2, case_title: '用例乙', status: 'failed' } as unknown as BatchTask,
    ]
    const wrapper = mountDialog()
    await flushPromises()

    expect(wrapper.find('.history-section').exists()).toBe(true)
    const rows = wrapper.findAll('.history-section .el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('用例甲')
    expect(rows[0].text()).toContain('completed')
    expect(rows[0].text()).toContain('3/4')
    expect(rows[1].text()).toContain('0/0')
  })
})

describe('BatchLocatorDialog — 配置视图交互', () => {
  it('定位方式与 AI 辅助双向绑定到组合式函数状态', async () => {
    state.visible.value = true
    const wrapper = mountDialog()
    await flushPromises()

    wrapper.findComponent({ name: 'ElRadioGroup' }).vm.$emit('update:modelValue', 'xpath')
    wrapper.findComponent({ name: 'ElSwitch' }).vm.$emit('update:modelValue', false)
    await nextTick()

    expect(state.locatorType.value).toBe('xpath')
    expect(state.aiAssist.value).toBe(false)
  })

  it('配置视图底部为「取消」+「开始定位」，分别触发 close 与 startLocate', async () => {
    state.visible.value = true
    const wrapper = mountDialog()
    await flushPromises()

    expect(footerButtons(wrapper)).toEqual(['取消', '开始定位'])

    await findFooterButton(wrapper, '开始定位')!.trigger('click')
    expect(mocks.startLocate).toHaveBeenCalledTimes(1)

    await findFooterButton(wrapper, '取消')!.trigger('click')
    expect(mocks.close).toHaveBeenCalledTimes(1)
  })

  it('loading 状态下「开始定位」按钮展示加载态', async () => {
    state.visible.value = true
    state.loading.value = true
    const wrapper = mountDialog()
    await flushPromises()

    const btn = wrapper
      .findAllComponents({ name: 'ElButton' })
      .find((item) => item.text().includes('开始定位'))
    expect(btn).toBeTruthy()
    expect(btn!.props('loading')).toBe(true)
  })
})

describe('BatchLocatorDialog — 进度视图', () => {
  it('展示进度、提示文案与成功失败统计', async () => {
    state.visible.value = true
    state.currentView.value = 'progress'
    state.selectedCaseIds.value = [1, 2, 3]
    state.progress.value = 40
    state.progressMessage.value = '正在定位... 2/5'
    state.successCount.value = 2
    state.failCount.value = 1
    const wrapper = mountDialog()
    await flushPromises()

    const section = wrapper.find('.progress-section')
    expect(section.exists()).toBe(true)
    expect(section.text()).toContain('正在定位... 2/5')
    expect(section.text()).toContain('总计: 3')
    expect(section.text()).toContain('成功: 2')
    expect(section.text()).toContain('失败: 1')
  })

  it('进度视图底部为「关闭」+「取消任务」', async () => {
    state.visible.value = true
    state.currentView.value = 'progress'
    const wrapper = mountDialog()
    await flushPromises()

    expect(footerButtons(wrapper)).toEqual(['关闭', '取消任务'])

    await findFooterButton(wrapper, '取消任务')!.trigger('click')
    expect(mocks.cancelTask).toHaveBeenCalledTimes(1)

    await findFooterButton(wrapper, '关闭')!.trigger('click')
    expect(mocks.close).toHaveBeenCalledTimes(1)
  })
})

describe('BatchLocatorDialog — 报告视图', () => {
  it('存在错误时展示错误提示条', async () => {
    state.visible.value = true
    state.currentView.value = 'report'
    state.error.value = '启动批量定位失败'
    const wrapper = mountDialog()
    await flushPromises()

    expect(wrapper.find('.report-section .el-alert').text()).toContain('启动批量定位失败')
  })

  it('无错误时不展示错误提示条', async () => {
    state.visible.value = true
    state.currentView.value = 'report'
    const wrapper = mountDialog()
    await flushPromises()

    expect(wrapper.find('.report-section .el-alert').exists()).toBe(false)
  })

  it('有结果时展示汇总区，无结果时隐藏', async () => {
    state.visible.value = true
    state.currentView.value = 'report'
    const empty = mountDialog()
    await flushPromises()
    expect(empty.find('.report-summary').exists()).toBe(false)

    state.hasResults.value = true
    const filled = mountDialog()
    await flushPromises()
    expect(filled.find('.report-summary').exists()).toBe(true)
  })

  it('结果表格按成功/失败渲染定位器或错误信息，缺省展示「未生成」', async () => {
    state.visible.value = true
    state.currentView.value = 'report'
    state.hasResults.value = true
    state.results.value = [
      { case_id: 1, case_title: '用例甲', status: 'success', locator: '#login-btn' },
      {
        case_id: 2,
        case_title: '用例乙',
        status: 'failed',
        error_message: '元素未找到',
      },
      { case_id: 3, case_title: '用例丙', status: 'failed' },
    ]
    const wrapper = mountDialog()
    await flushPromises()

    const rows = wrapper.findAll('.report-section .el-table__row')
    expect(rows).toHaveLength(3)
    expect(rows[0].text()).toContain('成功')
    expect(rows[0].text()).toContain('#login-btn')
    expect(rows[1].text()).toContain('失败')
    expect(rows[1].text()).toContain('元素未找到')
    expect(rows[2].text()).toContain('未生成')
  })

  it('存在失败项时展示「重试失败项」并触发 retryFailed', async () => {
    state.visible.value = true
    state.currentView.value = 'report'
    state.failCount.value = 2
    const wrapper = mountDialog()
    await flushPromises()

    const btn = findFooterButton(wrapper, '重试失败项')
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(mocks.retryFailed).toHaveBeenCalledTimes(1)
  })

  it('无失败项时不展示「重试失败项」', async () => {
    state.visible.value = true
    state.currentView.value = 'report'
    state.failCount.value = 0
    const wrapper = mountDialog()
    await flushPromises()

    expect(findFooterButton(wrapper, '重试失败项')).toBeFalsy()
  })

  it('存在成功项时展示「应用结果」并触发 applyResults', async () => {
    state.visible.value = true
    state.currentView.value = 'report'
    state.successCount.value = 1
    const wrapper = mountDialog()
    await flushPromises()

    const btn = findFooterButton(wrapper, '应用结果')
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(mocks.applyResults).toHaveBeenCalledTimes(1)
  })

  it('无成功项时不展示「应用结果」', async () => {
    state.visible.value = true
    state.currentView.value = 'report'
    state.successCount.value = 0
    const wrapper = mountDialog()
    await flushPromises()

    expect(findFooterButton(wrapper, '应用结果')).toBeFalsy()
  })
})
