import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({ previewGraphPrompt: vi.fn() }))

vi.mock('@/api/case', () => ({
  caseApi: { previewGraphPrompt: mocks.previewGraphPrompt },
}))

import FlowPromptPreviewDialog from '../FlowPromptPreviewDialog.vue'

/** 真实 el-dialog 依赖 teleport/过渡，改用可派发 open/closed 的桩 */
const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  emits: ['update:modelValue', 'open', 'closed'],
  setup(props, { slots, emit }) {
    watch(
      () => props.modelValue,
      (value, old) => {
        if (value && !old) nextTick(() => emit('open'))
        if (!value && old) emit('closed')
      },
      { immediate: true }
    )
    return () =>
      props.modelValue
        ? h('div', { class: 'el-dialog', 'data-title': props.title }, [
            h('div', { class: 'el-dialog__body' }, slots.default?.()),
            h('div', { class: 'el-dialog__footer' }, slots.footer?.()),
          ])
        : null
  },
})

const stubs = { ElDialog: ElDialogStub }

function makePreview(over: Record<string, unknown> = {}) {
  return {
    graph_prompt: '## 流程图\n1. 打开首页',
    node_count: 8,
    edge_count: 7,
    main_count: 1,
    branch_count: 4,
    exception_count: 2,
    bypass_count: 1,
    errors: [],
    warnings: [],
    ...over,
  }
}

async function mountDialog(props: Record<string, unknown> = {}) {
  const wrapper = mount(FlowPromptPreviewDialog, {
    props: {
      visible: true,
      flowSortData: { nodes: [{ id: 1 }] },
      context: { project_name: 'Alpha' },
      'onUpdate:visible': vi.fn(),
      ...props,
    },
    global: { stubs },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mocks.previewGraphPrompt.mockResolvedValue({ data: { code: 0, data: makePreview(), msg: '' } })
})

describe('FlowPromptPreviewDialog — 打开预览', () => {
  it('打开时按当前流程图与上下文请求预览', async () => {
    await mountDialog()

    expect(mocks.previewGraphPrompt).toHaveBeenCalledWith({
      flow_sort_data: { nodes: [{ id: 1 }] },
      context: { project_name: 'Alpha' },
    })
  })

  it('未传 context 时以空对象请求', async () => {
    await mountDialog({ context: undefined })

    expect(mocks.previewGraphPrompt).toHaveBeenCalledWith(expect.objectContaining({ context: {} }))
  })

  it('渲染节点/连线/主干/分支/异常/弹窗统计', async () => {
    const wrapper = await mountDialog()

    const stats = wrapper.findAll('.stat-value').map((node) => node.text())
    expect(stats).toEqual(['8', '7', '1', '4', '2', '1'])
  })

  it('渲染结构错误与建议优化列表', async () => {
    mocks.previewGraphPrompt.mockResolvedValue({
      data: {
        code: 0,
        data: makePreview({
          errors: [{ msg: '缺少开始节点' }],
          warnings: [{ msg: '存在孤立节点' }, { msg: '分支过深' }],
        }),
        msg: '',
      },
    })

    const wrapper = await mountDialog()

    const errorBlock = wrapper.find('.preview-issues--error')
    expect(errorBlock.text()).toContain('结构错误（1）')
    expect(errorBlock.text()).toContain('缺少开始节点')

    const warningBlock = wrapper.find('.preview-issues--warning')
    expect(warningBlock.text()).toContain('建议优化（2）')
    expect(warningBlock.text()).toContain('分支过深')
  })

  it('无错误与警告时不渲染问题区块', async () => {
    const wrapper = await mountDialog()

    expect(wrapper.find('.preview-issues--error').exists()).toBe(false)
    expect(wrapper.find('.preview-issues--warning').exists()).toBe(false)
  })

  it('渲染完整 Prompt 文本', async () => {
    const wrapper = await mountDialog()

    expect(wrapper.find('.prompt-content').text()).toContain('打开首页')
  })
})

describe('FlowPromptPreviewDialog — 复制', () => {
  it('复制成功提示已复制', async () => {
    const wrapper = await mountDialog()

    const copyBtn = wrapper.findAll('.el-button').find((node) => node.text().includes('复制'))!
    await copyBtn.trigger('click')
    await flushPromises()

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('## 流程图\n1. 打开首页')
    expect(ElMessage.success).toHaveBeenCalledWith('已复制到剪贴板')
  })

  it('复制失败提示手动复制', async () => {
    vi.mocked(navigator.clipboard.writeText).mockRejectedValueOnce(new Error('denied'))
    const wrapper = await mountDialog()

    const copyBtn = wrapper.findAll('.el-button').find((node) => node.text().includes('复制'))!
    await copyBtn.trigger('click')
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('复制失败，请手动复制')
  })
})

describe('FlowPromptPreviewDialog — 异常处理', () => {
  it('后端返回字符串 detail 时提示并关闭弹窗', async () => {
    mocks.previewGraphPrompt.mockRejectedValue({
      response: { data: { detail: '流程图存在未解析节点' } },
    })

    const wrapper = await mountDialog()

    expect(ElMessage.error).toHaveBeenCalledWith('流程图存在未解析节点')
    expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
  })

  it('后端返回对象 detail 时序列化提示', async () => {
    mocks.previewGraphPrompt.mockRejectedValue({
      response: { data: { detail: { nodes: [1, 2] } } },
    })

    await mountDialog()

    expect(ElMessage.error).toHaveBeenCalledWith(JSON.stringify({ nodes: [1, 2] }))
  })

  it('普通异常使用 error.message', async () => {
    mocks.previewGraphPrompt.mockRejectedValue(new Error('网络中断'))

    await mountDialog()

    expect(ElMessage.error).toHaveBeenCalledWith('网络中断')
  })

  it('无任何错误信息时使用兜底文案', async () => {
    mocks.previewGraphPrompt.mockRejectedValue(undefined)

    await mountDialog()

    expect(ElMessage.error).toHaveBeenCalledWith('预览失败')
  })
})

describe('FlowPromptPreviewDialog — 关闭', () => {
  it('关闭按钮写回 visible=false', async () => {
    const wrapper = await mountDialog()

    const closeBtn = wrapper.findAll('.el-button').find((node) => node.text() === '关闭')!
    await closeBtn.trigger('click')

    expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
  })

  it('关闭后清空预览数据', async () => {
    const wrapper = await mountDialog()
    expect(wrapper.find('.prompt-content').exists()).toBe(true)

    await wrapper.setProps({ visible: false })
    await flushPromises()

    expect(wrapper.find('.prompt-content').exists()).toBe(false)
  })
})
