import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import EdgeSuggestionDialog from '../EdgeSuggestionDialog.vue'
import type { FlowEditorNode } from '@/composables/useFlowEditor'

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: {
    modelValue: { type: Boolean, default: false },
    title: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'open', 'close', 'opened'],
  template: `
    <div v-if="modelValue" class="el-dialog">
      <h3 class="el-dialog__title">{{ title }}</h3>
      <slot />
      <div class="el-dialog__footer"><slot name="footer" /></div>
    </div>
  `,
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: { disabled: { type: Boolean, default: false }, type: { type: String, default: '' } },
  emits: ['click'],
  template: `<button class="el-button" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: '' } },
  template: '<span class="el-tag"><slot /></span>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

function node(id: string, name: string): FlowEditorNode {
  return {
    id,
    position: { x: 0, y: 0 },
    data: { screen_name: name, ui_spec_elements: [], flow_type: 'main' },
  } as unknown as FlowEditorNode
}

const stubs = {
  ElDialog: ElDialogStub,
  ElButton: ElButtonStub,
  ElTag: ElTagStub,
  ElIcon: ElIconStub,
}

function mountDialog(props: Record<string, unknown> = {}) {
  return mount(EdgeSuggestionDialog, {
    props: { visible: true, nodes: [], edges: [], ...props },
    global: { stubs },
  })
}

async function openDialog(wrapper: ReturnType<typeof mountDialog>) {
  wrapper.findComponent(ElDialogStub).vm.$emit('open')
  await nextTick()
  await nextTick()
}

describe('EdgeSuggestionDialog — 空态与列表', () => {
  it('无建议时展示空态提示', async () => {
    const wrapper = mountDialog({ nodes: [node('a', '登录页'), node('b', '购物车')] })

    await openDialog(wrapper)

    expect(wrapper.find('.empty-state').text()).toContain('未发现页面跳转关系')
    expect(wrapper.find('.suggestion-list').exists()).toBe(false)
  })

  it('有建议时渲染连线、相似度与原因', async () => {
    const wrapper = mountDialog({ nodes: [node('a', 'Login'), node('b', 'login')] })

    await openDialog(wrapper)

    expect(wrapper.find('.list-header').text()).toContain('共 2 条建议连线')
    const items = wrapper.findAll('.suggestion-item')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('Login')
    expect(items[0].text()).toContain('100%')
    expect(items[0].text()).toContain('页面名称')
  })
})

describe('EdgeSuggestionDialog — 单选与批量操作', () => {
  it('接受单条后按钮可用且计数变化', async () => {
    const wrapper = mountDialog({ nodes: [node('a', 'Login'), node('b', 'login')] })
    await openDialog(wrapper)

    const applyBtn = () => wrapper.findAll('button').find((b) => b.text().startsWith('应用'))!
    expect(applyBtn().attributes('disabled')).toBeDefined()

    const acceptBtn = wrapper.findAll('button').find((b) => b.text() === '接受')!
    await acceptBtn.trigger('click')

    expect(wrapper.findAll('.suggestion-item')[0].classes()).toContain('accepted')
    expect(applyBtn().text()).toBe('应用 1 条连线')
    expect(applyBtn().attributes('disabled')).toBeUndefined()
  })

  it('撤销已接受的建议', async () => {
    const wrapper = mountDialog({ nodes: [node('a', 'Login'), node('b', 'login')] })
    await openDialog(wrapper)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === '接受')!
      .trigger('click')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '撤销')!
      .trigger('click')

    expect(wrapper.find('.suggestion-item').classes()).not.toContain('accepted')
    expect(
      wrapper
        .findAll('button')
        .find((b) => b.text().startsWith('应用'))!
        .text()
    ).toBe('应用 0 条连线')
  })

  it('忽略后条目置灰且不再计入可应用数', async () => {
    const wrapper = mountDialog({ nodes: [node('a', 'Login'), node('b', 'login')] })
    await openDialog(wrapper)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === '忽略')!
      .trigger('click')

    expect(wrapper.find('.suggestion-item').classes()).toContain('ignored')
    expect(
      wrapper
        .findAll('button')
        .find((b) => b.text().startsWith('应用'))!
        .text()
    ).toBe('应用 0 条连线')
  })

  it('全部接受跳过已忽略项', async () => {
    const wrapper = mountDialog({ nodes: [node('a', 'Login'), node('b', 'login')] })
    await openDialog(wrapper)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === '忽略')!
      .trigger('click')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '全部接受')!
      .trigger('click')

    expect(wrapper.findAll('.suggestion-item')[0].classes()).not.toContain('accepted')
    expect(
      wrapper
        .findAll('button')
        .find((b) => b.text().startsWith('应用'))!
        .text()
    ).toBe('应用 1 条连线')
  })

  it('全部忽略后无可应用项', async () => {
    const wrapper = mountDialog({ nodes: [node('a', 'Login'), node('b', 'login')] })
    await openDialog(wrapper)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === '全部忽略')!
      .trigger('click')

    expect(wrapper.findAll('.suggestion-item.ignored')).toHaveLength(2)
    expect(
      wrapper
        .findAll('button')
        .find((b) => b.text().startsWith('应用'))!
        .text()
    ).toBe('应用 0 条连线')
  })
})

describe('EdgeSuggestionDialog — 确认回传', () => {
  it('仅回传已接受且未忽略的建议，并关闭弹窗', async () => {
    const wrapper = mountDialog({ nodes: [node('a', 'Login'), node('b', 'login')] })
    await openDialog(wrapper)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === '接受')!
      .trigger('click')
    await wrapper
      .findAll('button')
      .find((b) => b.text().startsWith('应用'))!
      .trigger('click')

    const emitted = wrapper.emitted('confirm')
    expect(emitted).toHaveLength(1)
    const accepted = emitted![0][0] as unknown as Array<{ sourceNodeId: string; accepted: boolean }>
    expect(accepted).toHaveLength(1)
    expect(accepted[0]).toMatchObject({ sourceNodeId: 'a', targetNodeId: 'b', accepted: true })

    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })

  it('关闭按钮直接收起弹窗', async () => {
    const wrapper = mountDialog({ nodes: [] })
    await openDialog(wrapper)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === '关闭')!
      .trigger('click')

    expect(wrapper.emitted('update:visible')).toEqual([[false]])
    expect(wrapper.emitted('confirm')).toBeUndefined()
  })
})
