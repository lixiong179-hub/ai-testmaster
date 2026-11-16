import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick, ref } from 'vue'

const state = vi.hoisted(() => ({
  currentStep: null as unknown,
  selectedFile: null as unknown,
  loading: null as unknown,
  importResult: null as unknown,
  handlePreview: null as unknown,
  handleImport: null as unknown,
  resetState: null as unknown,
}))

vi.mock('@/components/xmind/useXmindImport', () => ({
  XmindImportKey: Symbol('XmindImportMock'),
  useXmindImport: () => ({
    currentStep: state.currentStep,
    selectedFile: state.selectedFile,
    loading: state.loading,
    importResult: state.importResult,
    handlePreview: state.handlePreview,
    handleImport: state.handleImport,
    resetState: state.resetState,
  }),
}))

import XmindImportDialog from '../XmindImportDialog.vue'

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  emits: ['update:modelValue', 'close'],
  template: `
    <div v-if="modelValue" class="el-dialog">
      <slot />
      <div class="el-dialog__footer"><slot name="footer" /></div>
    </div>
  `,
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
  },
  emits: ['click'],
  template: `<button class="el-button" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
})

const ElStepsStub = defineComponent({
  name: 'ElSteps',
  template: '<div class="el-steps"><slot /></div>',
})

const ElStepStub = defineComponent({
  name: 'ElStep',
  props: { title: { type: String, default: '' } },
  template: '<span class="el-step">{{ title }}</span>',
})

const ElAlertStub = defineComponent({
  name: 'ElAlert',
  props: { title: { type: String, default: '' }, type: { type: String, default: '' } },
  template: '<div class="el-alert" :data-type="type">{{ title }}<slot name="title" /></div>',
})

const ElStatisticStub = defineComponent({
  name: 'ElStatistic',
  props: { title: { type: String, default: '' }, value: { type: [Number, String], default: 0 } },
  template: '<div class="el-statistic">{{ title }}:{{ value }}</div>',
})

const ElCollapseStub = defineComponent({
  name: 'ElCollapse',
  template: '<div class="el-collapse"><slot /></div>',
})

const ElCollapseItemStub = defineComponent({
  name: 'ElCollapseItem',
  props: { title: { type: String, default: '' } },
  template: '<div class="el-collapse-item">{{ title }}<slot /></div>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  template: '<span class="el-tag"><slot /></span>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

function defaultResult(overrides: Record<string, unknown> = {}) {
  return {
    success: true,
    savedCount: 12,
    savedCaseCount: 3,
    totalParsed: 15,
    skippedCount: 0,
    skippedReasons: [],
    errorMessage: '',
    aiTimeout: false,
    ...overrides,
  }
}

function setup(options: { step?: number; file?: unknown; result?: Record<string, unknown> } = {}) {
  state.currentStep = ref(options.step ?? 0)
  state.selectedFile = ref(options.file ?? null)
  state.loading = ref(false)
  state.importResult = ref(defaultResult(options.result))
  state.handlePreview = vi.fn()
  state.handleImport = vi.fn()
  state.resetState = vi.fn()

  const wrapper = mount(XmindImportDialog, {
    props: { projectId: 9, visible: true },
    global: {
      stubs: {
        ElDialog: ElDialogStub,
        ElButton: ElButtonStub,
        ElSteps: ElStepsStub,
        ElStep: ElStepStub,
        ElAlert: ElAlertStub,
        ElStatistic: ElStatisticStub,
        ElCollapse: ElCollapseStub,
        ElCollapseItem: ElCollapseItemStub,
        ElTag: ElTagStub,
        ElIcon: ElIconStub,
        XmindUploadStep: true,
        XmindPreviewStep: true,
      },
    },
  })
  return { wrapper, mgmt: state }
}

const buttonByText = (wrapper: ReturnType<typeof setup>['wrapper'], text: string) =>
  wrapper.findAll('button').find((b) => b.text() === text)

describe('XmindImportDialog — 步骤导航', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('上传步骤：未选文件时预览禁用，选中后可用并触发 handlePreview', async () => {
    const { wrapper } = setup({ step: 0, file: null })

    expect(buttonByText(wrapper, '取消')).toBeDefined()
    expect(buttonByText(wrapper, '预览')!.attributes('disabled')).toBeDefined()

    await wrapper.setProps({ visible: true })
    ;(state.selectedFile as { value: unknown }).value = new File(['x'], 'a.xmind')
    await nextTick()
    expect(buttonByText(wrapper, '预览')!.attributes('disabled')).toBeUndefined()

    await buttonByText(wrapper, '预览')!.trigger('click')
    expect(state.handlePreview).toHaveBeenCalledTimes(1)
  })

  it('预览步骤：重新选择回到上传步，确认导入调用 handleImport', async () => {
    const { wrapper } = setup({ step: 1 })

    await buttonByText(wrapper, '重新选择')!.trigger('click')
    expect((state.currentStep as { value: number }).value).toBe(0)
    ;(state.currentStep as { value: number }).value = 1
    await nextTick()
    await buttonByText(wrapper, '确认导入')!.trigger('click')
    expect(state.handleImport).toHaveBeenCalledTimes(1)
  })

  it('导入成功回调向外抛 imported', async () => {
    const { wrapper } = setup({ step: 1 })

    await buttonByText(wrapper, '确认导入')!.trigger('click')
    const callback = (state.handleImport as ReturnType<typeof vi.fn>).mock.calls[0][0] as () => void
    callback()

    expect(wrapper.emitted('imported')).toHaveLength(1)
  })

  it('结果步骤：继续导入重置状态，查看测试点关闭并抛事件', async () => {
    const { wrapper } = setup({ step: 2, result: { success: true } })

    await buttonByText(wrapper, '继续导入')!.trigger('click')
    expect(state.resetState).toHaveBeenCalledTimes(1)

    await buttonByText(wrapper, '查看测试点')!.trigger('click')
    expect(wrapper.emitted('update:visible')).toEqual([[false]])
    expect(wrapper.emitted('imported')).toHaveLength(1)
  })

  it('取消关闭弹窗并重置状态', async () => {
    const { wrapper } = setup({ step: 0 })

    await buttonByText(wrapper, '取消')!.trigger('click')

    expect(wrapper.emitted('update:visible')).toEqual([[false]])
    expect(state.resetState).toHaveBeenCalledTimes(1)
  })
})

describe('XmindImportDialog — 结果区', () => {
  it('成功态展示统计（跳过为 0 时不显示跳过项）', () => {
    const { wrapper } = setup({ step: 2 })

    const text = wrapper.find('.result-success').text()
    expect(text).toContain('导入成功')
    expect(wrapper.findAll('.el-statistic').map((s) => s.text())).toEqual([
      '成功导入:12',
      '生成用例:3',
      '解析总数:15',
    ])
  })

  it('存在跳过时展示跳过统计与原因折叠', () => {
    const { wrapper } = setup({
      step: 2,
      result: { skippedCount: 2, skippedReasons: ['缺少前置条件', '重复节点'] },
    })

    expect(wrapper.find('.el-statistic:nth-child(4)')).toBeDefined()
    const text = wrapper.find('.result-success').text()
    expect(text).toContain('跳过:2')
    expect(wrapper.find('.skipped-reasons').text()).toContain('查看跳过原因')
    expect(wrapper.findAll('.el-tag').map((t) => t.text())).toEqual(['缺少前置条件', '重复节点'])
  })

  it('AI 增强超时时展示降级提示', () => {
    const { wrapper } = setup({ step: 2, result: { aiTimeout: true } })

    const alert = wrapper.find('.result-ai-timeout-alert')
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('AI增强解析超时')
  })

  it('失败态展示错误信息且不显示查看测试点', () => {
    const { wrapper } = setup({
      step: 2,
      result: { success: false, errorMessage: '文件解析失败' },
    })

    expect(wrapper.find('.result-error').text()).toContain('导入失败')
    expect(wrapper.find('.result-error').text()).toContain('文件解析失败')
    expect(buttonByText(wrapper, '查看测试点')).toBeUndefined()
  })
})
