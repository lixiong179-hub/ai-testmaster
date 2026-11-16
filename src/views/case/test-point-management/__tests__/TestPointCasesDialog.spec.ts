import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, inject, ref } from 'vue'
import { ElMessage } from 'element-plus'

const mocks = vi.hoisted(() => ({ getRelatedCases: vi.fn() }))

vi.mock('@/api/testPoint', () => ({
  testPointApi: { getRelatedCases: mocks.getRelatedCases },
}))

import TestPointCasesDialog from '../TestPointCasesDialog.vue'

const ROWS_KEY = Symbol('rows')

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  emits: ['close', 'update:modelValue'],
  template: `<div class="el-dialog" v-if="modelValue" :data-title="title">
    <div class="el-dialog__body"><slot /></div>
  </div>`,
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: 'primary' }, effect: { type: String, default: 'light' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElTableStub = defineComponent({
  name: 'ElTable',
  props: { data: { type: Array, default: () => [] } },
  template: `<div class="el-table" :data-rows="data.length">
    <div v-if="data.length" class="el-table__body"><slot /></div>
    <div v-else class="el-table__empty"><slot name="empty" /></div>
  </div>`,
})

const ElTableColumnStub = defineComponent({
  name: 'ElTableColumn',
  props: { prop: { type: String, default: '' }, label: { type: String, default: '' } },
  setup(props, { slots }) {
    const rowsRef = inject<{ value: Array<Record<string, unknown>> }>(ROWS_KEY, ref([]))
    return () =>
      h(
        'div',
        { class: 'el-table-column', 'data-prop': props.prop, 'data-label': props.label },
        rowsRef.value.map((row, index) =>
          h(
            'div',
            { class: 'el-table-cell' },
            slots.default ? slots.default({ row, $index: index }) : String(row[props.prop] ?? '')
          )
        )
      )
  },
})

const ElPaginationStub = defineComponent({
  name: 'ElPagination',
  props: {
    total: { type: Number, default: 0 },
    currentPage: { type: Number, default: 1 },
    pageSize: { type: Number, default: 10 },
  },
  emits: ['current-change', 'size-change', 'update:current-page', 'update:page-size'],
  template:
    '<div class="el-pagination" :data-total="total" :data-page="currentPage" :data-size="pageSize"></div>',
})

const stubs = {
  ElDialog: ElDialogStub,
  ElTag: ElTagStub,
  ElTable: ElTableStub,
  ElTableColumn: ElTableColumnStub,
  ElPagination: ElPaginationStub,
}

type CaseRow = {
  case_no: string
  title: string
  module: string
  priority: number
  case_type: string
  create_time: string
}

const caseRows: CaseRow[] = [
  {
    case_no: 'TC-001',
    title: '密码错误锁定',
    module: '登录中心',
    priority: 1,
    case_type: '功能',
    create_time: '2026-11-01 10:00',
  },
  {
    case_no: 'TC-002',
    title: '重复支付校验',
    module: '支付',
    priority: 3,
    case_type: '接口',
    create_time: '2026-11-02 11:00',
  },
]

const testPoint = {
  id: 5,
  project_id: 9,
  module: '登录中心',
  point: '账号锁定策略',
  priority: 1,
  create_time: '2026-11-01',
}

type DialogProps = {
  modelValue: boolean
  testPoint: Record<string, unknown> | null
}

function setup(overrides: Partial<DialogProps> = {}) {
  const props: DialogProps = {
    modelValue: false,
    testPoint,
    ...overrides,
  }
  const wrapper = mount(TestPointCasesDialog, {
    props: props as never,
    global: {
      stubs,
      provide: { [ROWS_KEY]: ref<CaseRow[]>(caseRows) },
    },
  })
  return { wrapper }
}

async function open(props: Partial<DialogProps> = {}) {
  const { wrapper } = setup(props)
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(ElMessage, 'error').mockImplementation(() => ({}) as never)
  mocks.getRelatedCases.mockResolvedValue({ items: caseRows, total: 2 })
})

describe('TestPointCasesDialog — 打开与数据', () => {
  it('打开时按测试点分页查询关联用例', async () => {
    const wrapper = await open()

    expect(mocks.getRelatedCases).toHaveBeenCalledWith(5, 9, 1, 10)
    expect(wrapper.find('.el-dialog').attributes('data-title')).toBe('关联用例 - 账号锁定策略')
    expect(wrapper.findAll('.hero-meta .el-tag').map((t) => t.text())).toEqual([
      '共 2 条',
      '登录中心',
    ])
    expect(wrapper.find('.hero-title').text()).toBe('查看当前测试点关联的测试用例')
  })

  it('关闭状态不请求数据', () => {
    setup()

    expect(mocks.getRelatedCases).not.toHaveBeenCalled()
  })

  it('无测试点时即使打开也不请求', async () => {
    await open({ testPoint: null })

    expect(mocks.getRelatedCases).not.toHaveBeenCalled()
  })

  it('模块为空时不展示模块标签', async () => {
    const wrapper = await open({ testPoint: { ...testPoint, module: '' } })

    expect(wrapper.findAll('.hero-meta .el-tag')).toHaveLength(1)
  })

  it('用例表按列渲染字段与优先级标签', async () => {
    const wrapper = await open()
    const cells = (prop: string) =>
      wrapper.findAll(`.el-table-column[data-prop="${prop}"] .el-table-cell`)

    expect(wrapper.findComponent(ElTableStub).attributes('data-rows')).toBe('2')
    expect(cells('case_no').map((c) => c.text())).toEqual(['TC-001', 'TC-002'])
    expect(cells('title').map((c) => c.text())).toEqual(['密码错误锁定', '重复支付校验'])
    expect(cells('module').map((c) => c.text())).toEqual(['登录中心', '支付'])
    expect(cells('case_type').map((c) => c.text())).toEqual(['功能', '接口'])
    expect(cells('create_time').map((c) => c.text())).toEqual([
      '2026-11-01 10:00',
      '2026-11-02 11:00',
    ])

    const tags = wrapper.findAll('.el-table-column[data-prop="priority"] .el-tag')
    expect(tags.map((t) => t.text())).toEqual(['高', '低'])
    expect(tags.map((t) => t.attributes('data-type'))).toEqual(['danger', 'info'])
  })

  it('空数据展示引导文案', async () => {
    mocks.getRelatedCases.mockResolvedValue({ items: [], total: 0 })
    const wrapper = await open()

    expect(wrapper.find('.cases-empty-state').text()).toContain('当前测试点还没有关联用例')
  })

  it('加载失败提示并清空数量', async () => {
    mocks.getRelatedCases.mockRejectedValue(new Error('接口异常'))
    const wrapper = await open()

    expect(ElMessage.error).toHaveBeenCalledWith('接口异常')
    expect(wrapper.findAll('.hero-meta .el-tag')[0].text()).toBe('共 0 条')
  })
})

describe('TestPointCasesDialog — 分页', () => {
  it('翻页按新页码重新查询', async () => {
    const wrapper = await open()
    mocks.getRelatedCases.mockClear()

    const pagination = wrapper.findComponent(ElPaginationStub)
    pagination.vm.$emit('update:current-page', 2)
    pagination.vm.$emit('current-change', 2)
    await flushPromises()

    expect(mocks.getRelatedCases).toHaveBeenCalledWith(5, 9, 2, 10)
  })

  it('修改页长重置到第一页', async () => {
    const wrapper = await open()
    mocks.getRelatedCases.mockClear()

    wrapper.findComponent(ElPaginationStub).vm.$emit('size-change', 50)
    await flushPromises()

    expect(mocks.getRelatedCases).toHaveBeenCalledWith(5, 9, 1, 50)
    expect(wrapper.findComponent(ElPaginationStub).attributes('data-size')).toBe('50')
  })

  it('分页展示总数', async () => {
    const wrapper = await open()

    expect(wrapper.findComponent(ElPaginationStub).attributes('data-total')).toBe('2')
  })
})
