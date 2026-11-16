import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, type VNode } from 'vue'

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('@/api/case', () => ({
  testCaseApi: { getLineage: vi.fn() },
}))

import { testCaseApi } from '@/api/case'
import LineageTree from '../LineageTree.vue'

const getLineageMock = vi.mocked(testCaseApi.getLineage)

type LineageNode = {
  id: number
  case_no: string
  title: string
  lifecycle_status: string
  children?: LineageNode[]
}

const ElSkeletonStub = defineComponent({
  name: 'ElSkeleton',
  template: '<div class="el-skeleton" />',
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template: '<div class="el-empty">{{ description }}</div>',
})

const ElDescriptionsStub = defineComponent({
  name: 'ElDescriptions',
  template: '<div class="el-descriptions"><slot /></div>',
})

const ElDescriptionsItemStub = defineComponent({
  name: 'ElDescriptionsItem',
  props: { label: { type: String, default: '' } },
  template: '<div class="el-descriptions-item" :data-label="label"><slot /></div>',
})

const ElLinkStub = defineComponent({
  name: 'ElLink',
  emits: ['click'],
  template: '<a class="el-link" @click="$emit(\'click\')"><slot /></a>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: '' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElAlertStub = defineComponent({
  name: 'ElAlert',
  template: '<div class="el-alert"><slot name="title" /></div>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElTreeStub = defineComponent({
  name: 'ElTree',
  props: { data: { type: Array, default: () => [] } },
  setup(props, { slots }) {
    const renderNodes = (nodes: LineageNode[]): VNode[] =>
      nodes.flatMap((node) => [
        h('div', { class: 'tree-row' }, slots.default?.({ data: node })),
        ...(node.children ? renderNodes(node.children) : []),
      ])
    return () => h('div', { class: 'el-tree' }, renderNodes(props.data as LineageNode[]))
  },
})

const stubs = {
  ElSkeleton: ElSkeletonStub,
  ElEmpty: ElEmptyStub,
  ElDescriptions: ElDescriptionsStub,
  ElDescriptionsItem: ElDescriptionsItemStub,
  ElLink: ElLinkStub,
  ElTag: ElTagStub,
  ElAlert: ElAlertStub,
  ElIcon: ElIconStub,
  ElTree: ElTreeStub,
}

function lineage(overrides: Record<string, unknown> = {}) {
  return {
    root: {
      id: 10,
      case_no: 'TC-010',
      title: '根用例',
      lifecycle_status: 'active',
      children: [
        {
          id: 11,
          case_no: 'TC-011',
          title: '子用例',
          lifecycle_status: 'draft',
          children: [{ id: 12, case_no: 'TC-012', title: '孙用例', lifecycle_status: 'archived' }],
        },
      ],
    },
    ancestors: [
      { id: 1, case_no: 'TC-001', title: '祖先一', lifecycle_status: 'active' },
      { id: 10, case_no: 'TC-010', title: '当前用例', lifecycle_status: 'active' },
    ],
    chain_length: 3,
    warning_threshold: 3,
    warning: true,
    ...overrides,
  }
}

function mountTree(caseId = 10) {
  return mount(LineageTree, { props: { caseId }, global: { stubs } })
}

describe('LineageTree — 加载与错误态', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('请求中展示骨架屏', async () => {
    let resolveFn: ((value: unknown) => void) | undefined
    getLineageMock.mockReturnValue(
      new Promise((resolve) => {
        resolveFn = resolve
      }) as never
    )

    const wrapper = mountTree()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.lineage-loading').exists()).toBe(true)

    resolveFn?.(lineage())
    await flushPromises()

    expect(wrapper.find('.lineage-loading').exists()).toBe(false)
  })

  it('请求失败展示错误描述', async () => {
    getLineageMock.mockRejectedValue(new Error('网络错误'))

    const wrapper = mountTree()
    await flushPromises()

    expect(wrapper.find('.lineage-error').text()).toBe('加载血缘数据失败: 网络错误')
  })

  it('caseId 为 0 时不发起请求并展示空态', async () => {
    const wrapper = mountTree(0)
    await flushPromises()

    expect(getLineageMock).not.toHaveBeenCalled()
    expect(wrapper.find('.lineage-empty').text()).toBe('暂无血缘关系数据')
  })
})

describe('LineageTree — 摘要与警告', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getLineageMock.mockResolvedValue(lineage() as never)
  })

  it('展示根节点、链长度与阈值', async () => {
    const wrapper = mountTree()
    await flushPromises()

    const items = wrapper.findAll('.el-descriptions-item')
    expect(items.map((i) => i.attributes('data-label'))).toEqual(['根节点', '链长度', '警告阈值'])
    expect(wrapper.find('.el-link').text()).toBe('TC-010')
    expect(wrapper.text()).toContain('3')
  })

  it('超过阈值时展示拆分建议，未超阈值则不展示', async () => {
    const wrapper = mountTree()
    await flushPromises()
    expect(wrapper.find('.chain-warning').text()).toContain('建议拆分用例')

    getLineageMock.mockResolvedValue(lineage({ warning: false }) as never)
    const quiet = mountTree()
    await flushPromises()
    expect(quiet.find('.chain-warning').exists()).toBe(false)
  })

  it('点击根节点链接跳转用例详情，指向当前用例时不跳转', async () => {
    const current = mountTree(10)
    await flushPromises()
    await current.find('.el-link').trigger('click')
    expect(pushMock).not.toHaveBeenCalled()

    const other = mountTree(99)
    await flushPromises()
    await other.find('.el-link').trigger('click')
    expect(pushMock).toHaveBeenCalledWith({ name: 'CaseDetail', params: { caseId: '10' } })
  })
})

describe('LineageTree — 祖先链', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getLineageMock.mockResolvedValue(lineage() as never)
  })

  it('渲染祖先链并标记当前项', async () => {
    const wrapper = mountTree()
    await flushPromises()

    const items = wrapper.findAll('.ancestor-item')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('TC-001')
    expect(items[1].text()).toContain('TC-010')
    expect(items[1].classes()).toContain('is-current')
    expect(wrapper.findAll('.ancestor-arrow')).toHaveLength(1)
  })

  it('点击非当前祖先跳转，点击当前项不跳转', async () => {
    const wrapper = mountTree()
    await flushPromises()

    await wrapper.findAll('.ancestor-item')[1].trigger('click')
    expect(pushMock).not.toHaveBeenCalled()

    await wrapper.findAll('.ancestor-item')[0].trigger('click')
    expect(pushMock).toHaveBeenCalledWith({ name: 'CaseDetail', params: { caseId: '1' } })
  })

  it('生命周期标签按状态映射并回退原文', async () => {
    getLineageMock.mockResolvedValue(
      lineage({
        ancestors: [
          { id: 2, case_no: 'TC-002', title: '待评审', lifecycle_status: 'pending_review' },
          { id: 3, case_no: 'TC-003', title: '自定义', lifecycle_status: 'custom_status' },
        ],
      }) as never
    )

    const wrapper = mountTree()
    await flushPromises()

    const tags = wrapper.findAll('.ancestor-item .el-tag')
    expect(tags[0].text()).toBe('待评审')
    expect(tags[0].attributes('data-type')).toBe('warning')
    expect(tags[1].text()).toBe('custom_status')
    expect(tags[1].attributes('data-type')).toBe('info')
  })
})

describe('LineageTree — 后代树', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getLineageMock.mockResolvedValue(lineage() as never)
  })

  it('递归渲染后代并标记当前用例', async () => {
    const wrapper = mountTree()
    await flushPromises()

    expect(wrapper.findAll('.tree-node')).toHaveLength(3)
    expect(wrapper.findAll('.current-tag')).toHaveLength(1)
    expect(wrapper.find('.current-tag').text()).toBe('当前')
    expect(wrapper.text()).toContain('孙用例')
  })

  it('点击后代节点跳转用例详情', async () => {
    const wrapper = mountTree()
    await flushPromises()

    await wrapper.findAll('.tree-node')[1].trigger('click')

    expect(pushMock).toHaveBeenCalledWith({ name: 'CaseDetail', params: { caseId: '11' } })
  })

  it('caseId 变化时重新拉取', async () => {
    const wrapper = mountTree(10)
    await flushPromises()
    expect(getLineageMock).toHaveBeenCalledTimes(1)

    await wrapper.setProps({ caseId: 11 })
    await flushPromises()

    expect(getLineageMock).toHaveBeenCalledTimes(2)
    expect(getLineageMock).toHaveBeenLastCalledWith(11)
  })

  it('refresh 暴露方法可手动重载', async () => {
    const wrapper = mountTree()
    await flushPromises()

    await wrapper.vm.refresh()
    await flushPromises()

    expect(getLineageMock).toHaveBeenCalledTimes(2)
  })
})
