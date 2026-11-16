import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick, ref } from 'vue'

const mockCtx = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/flowSort/useFlowSortEditor', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/composables/flowSort/useFlowSortEditor')>()
  return {
    ...actual,
    useFlowSortEditor: () => ({
      FLOW_TYPE_TAG_MAP: actual.FLOW_TYPE_TAG_MAP,
      FLOW_TYPE_LABEL_MAP: actual.FLOW_TYPE_LABEL_MAP,
      ...mockCtx.current,
    }),
  }
})

import NodeDetailPanel from '../NodeDetailPanel.vue'

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: { type: { type: String, default: '' } },
  emits: ['click'],
  template: `<button class="el-button" :data-type="type" @click="$emit('click')"><slot /></button>`,
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: '' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElButtonGroupStub = defineComponent({
  name: 'ElButtonGroup',
  template: '<div class="el-button-group"><slot /></div>',
})

const stubs = {
  ElIcon: ElIconStub,
  ElButton: ElButtonStub,
  ElTag: ElTagStub,
  ElButtonGroup: ElButtonGroupStub,
}

type NodeData = {
  id: string
  screen_id: number
  screen_name: string
  summary?: string
  flow_type: 'main' | 'branch' | 'exception' | 'bypass'
  main_order?: number
  image_url?: string
  element_count?: number
}

function detailNode(overrides: Partial<NodeData> = {}): NodeData {
  return {
    id: 'n2',
    screen_id: 12,
    screen_name: '登录页',
    flow_type: 'main',
    main_order: 2,
    ...overrides,
  }
}

function setup(
  props: Partial<{
    visible: boolean
    nodeData: NodeData | null
    displayMode: 'overview' | 'edit'
  }> = {}
) {
  const vueFlowNodes = ref([
    { id: 'n1', data: { screen_name: '首页', flow_type: 'main' } },
    { id: 'n2', data: { screen_name: '登录页', flow_type: 'main' } },
    { id: 'n3', data: { screen_name: '异常页', flow_type: 'exception' } },
  ])
  const vueFlowEdges = ref([
    { id: 'e1', source: 'n1', target: 'n2' },
    { id: 'e2', source: 'n2', target: 'n3' },
    { id: 'e3', source: 'n2', target: 'n404', hidden: true },
  ])
  mockCtx.current = { vueFlowNodes, vueFlowEdges }

  const wrapper = mount(NodeDetailPanel, {
    props: { visible: true, nodeData: detailNode(), displayMode: 'overview', ...props },
    global: { stubs },
  })
  return { wrapper, vueFlowNodes, vueFlowEdges }
}

describe('NodeDetailPanel — 可见性', () => {
  it('visible 为 false 或 nodeData 为空时不渲染', () => {
    expect(setup({ visible: false }).wrapper.find('.node-detail-panel').exists()).toBe(false)
    expect(setup({ nodeData: null }).wrapper.find('.node-detail-panel').exists()).toBe(false)
  })
})

describe('NodeDetailPanel — 基本信息', () => {
  it('展示页面名、类型标签与主干步序', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.detail-name').text()).toBe('登录页')
    expect(wrapper.find('.detail-flow-type').text()).toBe('主干')
    expect(wrapper.find('.detail-flow-type').classes()).toContain('detail-flow-type--main')
    expect(wrapper.find('.detail-main-order').text()).toBe('主干第 2 步')
  })

  it('非主干类型不展示步序', () => {
    const { wrapper } = setup({
      nodeData: detailNode({ flow_type: 'branch', main_order: undefined }),
    })

    expect(wrapper.find('.detail-flow-type').text()).toBe('分支')
    expect(wrapper.find('.detail-main-order').exists()).toBe(false)
  })

  it('摘要与元素数量按需展示', () => {
    const withoutSummary = setup({ nodeData: detailNode({ element_count: 0 }) }).wrapper
    expect(withoutSummary.find('.detail-summary').exists()).toBe(false)
    expect(withoutSummary.text()).toContain('0 个元素')

    const withSummary = setup({
      nodeData: detailNode({ summary: '账号密码登录', element_count: 6 }),
    }).wrapper
    expect(withSummary.find('.detail-summary').text()).toBe('账号密码登录')
    expect(withSummary.text()).toContain('6 个元素')
  })
})

describe('NodeDetailPanel — 图片态', () => {
  it('无图片地址时展示占位文案', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.image-placeholder').text()).toContain('暂无图片')
    expect(wrapper.find('.image-preview-hint').exists()).toBe(false)
  })

  it('有图片时展示预览提示，加载完成后加 img-loaded', async () => {
    const { wrapper } = setup({ nodeData: detailNode({ image_url: 'https://x/1.png' }) })

    const img = wrapper.find('img')
    expect(img.exists()).toBe(true)
    expect(wrapper.find('.image-skeleton').exists()).toBe(true)
    expect(wrapper.find('.image-preview-hint').text()).toContain('点击预览大图')

    await img.trigger('load')

    expect(wrapper.find('.image-skeleton').exists()).toBe(false)
    expect(wrapper.find('img').classes()).toContain('img-loaded')
  })

  it('图片加载失败时回退失败文案', async () => {
    const { wrapper } = setup({ nodeData: detailNode({ image_url: 'https://x/1.png' }) })

    await wrapper.find('img').trigger('error')

    expect(wrapper.find('.image-placeholder').text()).toContain('加载失败')
    expect(wrapper.find('.image-preview-hint').exists()).toBe(false)
  })

  it('点击图片区抛 preview 事件', async () => {
    const { wrapper } = setup()

    await wrapper.find('.detail-image').trigger('click')

    expect(wrapper.emitted('preview')).toHaveLength(1)
  })

  it('切换图片地址后重置加载态', async () => {
    const { wrapper } = setup({ nodeData: detailNode({ image_url: 'https://x/1.png' }) })
    await wrapper.find('img').trigger('load')

    await wrapper.setProps({ nodeData: detailNode({ image_url: 'https://x/2.png' }) })
    await nextTick()

    expect(wrapper.find('.image-skeleton').exists()).toBe(true)
    expect(wrapper.find('img').classes()).not.toContain('img-loaded')
  })
})

describe('NodeDetailPanel — 上下游页面', () => {
  it('按连线计算上游与下游并跳过隐藏边/未知节点', () => {
    const { wrapper } = setup()

    const upstream = wrapper.findAll('.detail-section').filter((s) => s.text().includes('上游页面'))
    const downstream = wrapper
      .findAll('.detail-section')
      .filter((s) => s.text().includes('下游页面'))

    expect(upstream[0].findAll('.page-list-item')).toHaveLength(1)
    expect(upstream[0].text()).toContain('首页')
    expect(downstream[0].findAll('.page-list-item')).toHaveLength(1)
    expect(downstream[0].text()).toContain('异常页')
  })

  it('点击页面项抛 locate-node', async () => {
    const { wrapper } = setup()

    await wrapper.find('.page-list-item').trigger('click')

    expect(wrapper.emitted('locate-node')).toEqual([['n1']])
  })

  it('无连线时不渲染上下游区块', () => {
    const { wrapper, vueFlowEdges } = setup()
    vueFlowEdges.value = []

    return nextTick().then(() => {
      expect(wrapper.text()).not.toContain('上游页面')
      expect(wrapper.text()).not.toContain('下游页面')
    })
  })
})

describe('NodeDetailPanel — 编辑模式', () => {
  it('overview 模式不展示类型切换', () => {
    const { wrapper } = setup({ displayMode: 'overview' })

    expect(wrapper.find('.type-action-group').exists()).toBe(false)
  })

  it('edit 模式可切换流程类型', async () => {
    const { wrapper } = setup({ displayMode: 'edit' })

    const buttons = wrapper.findAll('.type-action-group .el-button')
    expect(buttons.map((b) => b.text())).toEqual(['主干', '分支', '异常', '弹窗'])
    expect(buttons[0].attributes('data-type')).toBe('primary')

    await buttons[1].trigger('click')

    expect(wrapper.emitted('flow-type-change')).toEqual([['branch']])
  })

  it('弹窗类型展示帮助文案', () => {
    const { wrapper } = setup({
      displayMode: 'edit',
      nodeData: detailNode({ flow_type: 'bypass' }),
    })

    expect(wrapper.find('.type-help-text').text()).toBe('自动出现，关闭后继续主流程')
  })
})

describe('NodeDetailPanel — 关闭', () => {
  it('点击关闭按钮抛 update:visible=false', async () => {
    const { wrapper } = setup()

    await wrapper.find('.panel-header .el-button').trigger('click')

    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })
})
