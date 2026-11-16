import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick, ref } from 'vue'

const mockCtx = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/flowSort/useFlowSortEditor', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/composables/flowSort/useFlowSortEditor')>()
  return { ...actual, useFlowSortEditor: () => mockCtx.current }
})

import MainStepList from '../MainStepList.vue'

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: '' } },
  template: '<span class="el-tag"><slot /></span>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  emits: ['click'],
  template: '<button class="el-button" @click="$emit(\'click\')"><slot /></button>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const stubs = {
  ElTag: ElTagStub,
  ElButton: ElButtonStub,
  ElIcon: ElIconStub,
  transition: false,
  'transition-group': false,
}

type NodeSpec = {
  id: string
  name: string
  order: number
  flowType?: 'main' | 'branch'
}

function node({ id, name, order, flowType = 'main' }: NodeSpec) {
  return {
    id,
    position: { x: 0, y: 0 },
    data: { screen_name: name, flow_type: flowType, main_order: order },
  }
}

function setup(
  options: {
    visible?: boolean
    activeNodeId?: string | null
    nodes?: NodeSpec[]
    edges?: Array<{ source: string; target: string }>
  } = {}
) {
  const nodes = options.nodes ?? [
    { id: 'n2', name: '首页', order: 2 },
    { id: 'n1', name: '登录页', order: 1 },
  ]
  const ctx = {
    vueFlowNodes: ref(nodes.map(node)),
    vueFlowEdges: ref(
      (options.edges ?? [{ source: 'n1', target: 'n2' }]).map((e, i) => ({
        id: `e${i}`,
        source: e.source,
        target: e.target,
        data: {},
      }))
    ),
  }
  mockCtx.current = ctx

  const wrapper = mount(MainStepList, {
    props: {
      visible: options.visible ?? true,
      activeNodeId: options.activeNodeId ?? null,
    },
    global: { stubs },
  })
  return { ctx, wrapper }
}

describe('MainStepList — 渲染', () => {
  it('不可见时不渲染面板', () => {
    const { wrapper } = setup({ visible: false })

    expect(wrapper.find('.main-step-list').exists()).toBe(false)
  })

  it('头部展示步数并可关闭', async () => {
    const { wrapper } = setup()

    expect(wrapper.find('.step-list-title').text()).toBe('主干步骤')
    expect(wrapper.find('.el-tag').text()).toBe('2 步')

    await wrapper.find('.step-list-header button').trigger('click')
    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })

  it('按 main_order 升序渲染序号与名称', () => {
    const { wrapper } = setup()

    expect(wrapper.findAll('.step-order').map((s) => s.text())).toEqual(['1', '2'])
    expect(wrapper.findAll('.step-name').map((s) => s.text())).toEqual(['登录页', '首页'])
  })

  it('忽略非主干节点', () => {
    const { wrapper } = setup({
      nodes: [
        { id: 'n1', name: '登录页', order: 1 },
        { id: 'b1', name: '分支页', order: 2, flowType: 'branch' },
      ],
    })

    expect(wrapper.findAll('.step-item')).toHaveLength(1)
    expect(wrapper.find('.el-tag').text()).toBe('1 步')
  })

  it('无主干节点时展示空态', () => {
    const { wrapper } = setup({ nodes: [] })

    expect(wrapper.find('.step-list-empty').text()).toBe('暂无主干节点')
    expect(wrapper.find('.el-tag').text()).toBe('0 步')
  })

  it('高亮当前节点', () => {
    const { wrapper } = setup({ activeNodeId: 'n2' })

    const items = wrapper.findAll('.step-item')
    expect(items[0].classes()).not.toContain('is-active')
    expect(items[1].classes()).toContain('is-active')
  })

  it('点击步骤抛 locate-node', async () => {
    const { wrapper } = setup()

    await wrapper.findAll('.step-item')[0].trigger('click')

    expect(wrapper.emitted('locate-node')).toEqual([['n1']])
  })
})

describe('MainStepList — 异常标记', () => {
  it('缺少或非法顺序号提示', () => {
    const { wrapper } = setup({
      nodes: [
        { id: 'n1', name: 'A', order: 0 },
        { id: 'n2', name: 'B', order: 2 },
      ],
    })

    const first = wrapper.findAll('.step-item')[0]
    expect(first.classes()).toContain('has-issue')
    expect(first.find('.step-issue').text()).toContain('缺少顺序号')
  })

  it('顺序号重复提示', () => {
    const { wrapper } = setup({
      nodes: [
        { id: 'n1', name: 'A', order: 1 },
        { id: 'n2', name: 'B', order: 1 },
      ],
      edges: [{ source: 'n1', target: 'n2' }],
    })

    const issues = wrapper.findAll('.step-issue').map((i) => i.text())
    expect(issues).toEqual([
      expect.stringContaining('顺序号重复'),
      expect.stringContaining('顺序号重复'),
    ])
  })

  it('孤立节点提示', () => {
    const { wrapper } = setup({
      nodes: [
        { id: 'n1', name: 'A', order: 1 },
        { id: 'n2', name: 'B', order: 2 },
      ],
      edges: [],
    })

    expect(wrapper.findAll('.step-issue').map((i) => i.text())).toEqual([
      expect.stringContaining('孤立节点'),
      expect.stringContaining('孤立节点'),
    ])
  })

  it('顺序断档提示', () => {
    const { wrapper } = setup({
      nodes: [
        { id: 'n1', name: 'A', order: 1 },
        { id: 'n2', name: 'B', order: 3 },
      ],
      edges: [{ source: 'n1', target: 'n2' }],
    })

    const items = wrapper.findAll('.step-item')
    expect(items[0].classes()).not.toContain('has-issue')
    expect(items[1].classes()).toContain('has-issue')
    expect(items[1].find('.step-issue').text()).toContain('顺序断档')
  })

  it('正常顺序不产生提示', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.step-issue').exists()).toBe(false)
    expect(wrapper.findAll('.has-issue')).toHaveLength(0)
  })
})

describe('MainStepList — 拖拽排序', () => {
  const dragEvent = () => ({ dataTransfer: { setData: vi.fn(), effectAllowed: '' } })

  it('拖拽过程标记 drag-over / is-dragging 并在结束后清除', async () => {
    const { wrapper } = setup()
    const items = wrapper.findAll('.step-item')

    await items[0].trigger('dragstart', dragEvent())
    expect(items[0].classes()).toContain('is-dragging')

    await items[1].trigger('dragover')
    expect(items[1].classes()).toContain('is-drag-over')

    await items[1].trigger('dragleave')
    expect(items[1].classes()).not.toContain('is-drag-over')

    await items[0].trigger('dragend')
    expect(wrapper.findAll('.step-item')[0].classes()).not.toContain('is-dragging')
  })

  it('放下时按目标位置重排并抛 reorder', async () => {
    const { wrapper } = setup({
      nodes: [
        { id: 'n1', name: 'A', order: 1 },
        { id: 'n2', name: 'B', order: 2 },
        { id: 'n3', name: 'C', order: 3 },
      ],
      edges: [
        { source: 'n1', target: 'n2' },
        { source: 'n2', target: 'n3' },
      ],
    })

    await wrapper.findAll('.step-item')[0].trigger('dragstart', dragEvent())
    await wrapper.findAll('.step-item')[2].trigger('drop')

    expect(wrapper.emitted('reorder')).toEqual([[['n2', 'n3', 'n1']]])
    expect(wrapper.findAll('.step-item')[2].classes()).not.toContain('is-drag-over')
  })

  it('同位置放下不触发重排', async () => {
    const { wrapper } = setup()

    await wrapper.findAll('.step-item')[1].trigger('dragstart', dragEvent())
    await wrapper.findAll('.step-item')[1].trigger('drop')

    expect(wrapper.emitted('reorder')).toBeUndefined()
  })

  it('未拖拽直接放下不触发重排', async () => {
    const { wrapper } = setup()

    await wrapper.findAll('.step-item')[1].trigger('drop')

    expect(wrapper.emitted('reorder')).toBeUndefined()
  })

  it('dragstart 写入拖拽索引供 drop 使用', async () => {
    const { wrapper } = setup({
      nodes: [
        { id: 'n1', name: 'A', order: 1 },
        { id: 'n2', name: 'B', order: 2 },
      ],
      edges: [{ source: 'n1', target: 'n2' }],
    })
    const dataTransfer = { setData: vi.fn(), effectAllowed: '' }

    await wrapper.findAll('.step-item')[1].trigger('dragstart', { dataTransfer })
    expect(dataTransfer.effectAllowed).toBe('move')
    expect(dataTransfer.setData).toHaveBeenCalledWith('text/plain', '1')

    await wrapper.findAll('.step-item')[0].trigger('drop')
    expect(wrapper.emitted('reorder')).toEqual([[['n2', 'n1']]])
  })

  it('节点顺序变化后列表同步更新', async () => {
    const { ctx, wrapper } = setup()
    expect(wrapper.findAll('.step-name').map((s) => s.text())).toEqual(['登录页', '首页'])
    ;(ctx.vueFlowNodes as { value: unknown[] }).value = [
      node({ id: 'n2', name: '首页', order: 1 }),
      node({ id: 'n1', name: '登录页', order: 2 }),
    ]
    await nextTick()

    expect(wrapper.findAll('.step-name').map((s) => s.text())).toEqual(['首页', '登录页'])
  })
})
