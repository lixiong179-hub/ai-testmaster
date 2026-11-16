import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, inject, ref } from 'vue'
import { TestPointMgmtKey } from '../../useTestPointManagement'
import TestPointTable from '../TestPointTable.vue'

const ROWS_KEY = Symbol('tableRows')

const ElCardStub = defineComponent({
  name: 'ElCard',
  template: '<div class="el-card"><slot /></div>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: 'primary' }, effect: { type: String, default: 'light' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    type: { type: String, default: '' },
    text: { type: Boolean, default: false },
    bg: { type: Boolean, default: false },
  },
  emits: ['click'],
  template:
    '<button class="el-button" :data-type="type" @click="$emit(\'click\')"><slot /></button>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElLinkStub = defineComponent({
  name: 'ElLink',
  props: { type: { type: String, default: '' } },
  emits: ['click'],
  template: '<a class="el-link" :data-type="type" @click="$emit(\'click\')"><slot /></a>',
})

const ElTableStub = defineComponent({
  name: 'ElTable',
  props: { data: { type: Array, default: () => [] } },
  emits: ['selection-change', 'sort-change'],
  template: `<div class="el-table">
    <div v-if="data.length" class="el-table__body"><slot /></div>
    <div v-else class="el-table__empty"><slot name="empty" /></div>
  </div>`,
})

const ElTableColumnStub = defineComponent({
  name: 'ElTableColumn',
  props: {
    prop: { type: String, default: '' },
    label: { type: String, default: '' },
    type: { type: String, default: '' },
    width: { type: [String, Number], default: '' },
  },
  setup(props, { slots }) {
    const rows = inject<Array<Record<string, unknown>>>(ROWS_KEY, [])
    return () =>
      h(
        'div',
        {
          class: 'el-table-column',
          'data-prop': props.prop,
          'data-label': props.label,
          'data-type': props.type,
        },
        rows.map((row, index) =>
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
  ElCard: ElCardStub,
  ElTag: ElTagStub,
  ElButton: ElButtonStub,
  ElIcon: ElIconStub,
  ElLink: ElLinkStub,
  ElTable: ElTableStub,
  ElTableColumn: ElTableColumnStub,
  ElPagination: ElPaginationStub,
}

type PointRow = {
  id: number
  module: string
  point: string
  priority: number
  created_by?: string
  create_time?: string
  test_case_count?: number
}

const rows: PointRow[] = [
  {
    id: 1,
    module: '登录中心',
    point: '密码错误三次锁定账号',
    priority: 1,
    created_by: '张三',
    create_time: '2026-11-01 10:00',
    test_case_count: 2,
  },
  {
    id: 2,
    module: '支付',
    point: '重复支付幂等校验',
    priority: 3,
    created_by: '李四',
    create_time: '2026-11-02 11:00',
  },
]

function setup(options: { data?: PointRow[]; selected?: PointRow[] } = {}) {
  const data = options.data ?? rows
  const ctx = {
    testPoints: ref(data),
    loading: ref(false),
    total: data.length,
    page: ref(1),
    pageSize: ref(10),
    selectedRows: ref(options.selected ?? []),
    handleSelectionChange: vi.fn(),
    handleSortChange: vi.fn(),
    handlePageSizeChange: vi.fn(),
    openCasesDialog: vi.fn(),
    handleGenerate: vi.fn(),
    openEditDialog: vi.fn(),
    handleDelete: vi.fn(),
    openExtractDialog: vi.fn(),
    openXmindImportDialog: vi.fn(),
    openCreateDialog: vi.fn(),
    handleBatchDelete: vi.fn(),
    handleBatchGenerate: vi.fn(),
    fetchTestPoints: vi.fn(),
    priorityText: (priority: number) => ({ 1: '高', 2: '中', 3: '低' })[priority] ?? '未知',
    priorityTagType: (priority: number) => ({ 1: 'danger', 2: 'warning', 3: 'info' })[priority],
  }
  const wrapper = mount(TestPointTable, {
    global: {
      stubs,
      provide: { [TestPointMgmtKey as symbol]: ctx, [ROWS_KEY]: data },
    },
  })
  return { ctx, wrapper }
}

function column(wrapper: ReturnType<typeof setup>['wrapper'], label: string) {
  return wrapper.find(`.el-table-column[data-label="${label}"]`)
}

describe('TestPointTable — 头部与批量操作', () => {
  it('展示总数标签', () => {
    const { wrapper } = setup()

    const tags = wrapper.findAll('.table-summary .el-tag')
    expect(tags).toHaveLength(1)
    expect(tags[0].text()).toBe('共 2 条')
  })

  it('已选行时展示数量标签与批量按钮', async () => {
    const { ctx, wrapper } = setup({ selected: [rows[0]] })

    expect(wrapper.findAll('.table-summary .el-tag')[1].text()).toBe('已选 1 条')
    expect(wrapper.find('.batch-actions').text()).toContain('已选择 1 条')

    const buttons = wrapper.findAll('.batch-action-buttons .el-button')
    expect(buttons.map((b) => b.text())).toEqual(['批量删除', '批量生成用例'])

    await buttons[0].trigger('click')
    await buttons[1].trigger('click')

    expect(ctx.handleBatchDelete).toHaveBeenCalledTimes(1)
    expect(ctx.handleBatchGenerate).toHaveBeenCalledTimes(1)
  })

  it('未选中时不展示批量操作区', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.batch-actions').exists()).toBe(false)
    expect(wrapper.findAll('.table-summary .el-tag')).toHaveLength(1)
  })
})

describe('TestPointTable — 列渲染', () => {
  it('模块列直接渲染字段值', () => {
    const { wrapper } = setup()

    expect(
      column(wrapper, '模块')
        .findAll('.el-table-cell')
        .map((c) => c.text())
    ).toEqual(['登录中心', '支付'])
  })

  it('测试点列展示描述与模块副标题', () => {
    const { wrapper } = setup()

    const cells = column(wrapper, '测试点').findAll('.el-table-cell')
    expect(cells[0].find('.point-text').text()).toBe('密码错误三次锁定账号')
    expect(cells[0].find('.point-meta').text()).toBe('登录中心')
  })

  it('优先级列按映射输出文案与颜色', () => {
    const { wrapper } = setup()

    const tags = column(wrapper, '优先级').findAll('.el-tag')
    expect(tags.map((t) => t.text())).toEqual(['高', '低'])
    expect(tags.map((t) => t.attributes('data-type'))).toEqual(['danger', 'info'])
  })

  it('已生成用例数列缺省显示 0 并可打开用例弹窗', async () => {
    const { ctx, wrapper } = setup()

    const links = column(wrapper, '已生成用例数').findAll('.el-link')
    expect(links.map((l) => l.text())).toEqual(['2', '0'])

    await links[0].trigger('click')
    expect(ctx.openCasesDialog).toHaveBeenCalledWith(rows[0])
  })

  it('创建人与创建时间列渲染字段值', () => {
    const { wrapper } = setup()

    expect(
      column(wrapper, '创建人')
        .findAll('.el-table-cell')
        .map((c) => c.text())
    ).toEqual(['张三', '李四'])
    expect(
      column(wrapper, '创建时间')
        .findAll('.el-table-cell')
        .map((c) => c.text())
    ).toEqual(['2026-11-01 10:00', '2026-11-02 11:00'])
  })

  it('操作列四个按钮分别转发对应动作', async () => {
    const { ctx, wrapper } = setup()

    const firstRowActions = column(wrapper, '操作').findAll('.action-group')[0]
    const buttons = firstRowActions.findAll('.el-button')
    expect(buttons.map((b) => b.text())).toEqual(['查看用例', '生成用例', '编辑', '删除'])

    for (const button of buttons) {
      await button.trigger('click')
    }

    expect(ctx.openCasesDialog).toHaveBeenCalledWith(rows[0])
    expect(ctx.handleGenerate).toHaveBeenCalledWith(rows[0])
    expect(ctx.openEditDialog).toHaveBeenCalledWith(rows[0])
    expect(ctx.handleDelete).toHaveBeenCalledWith(rows[0])
  })
})

describe('TestPointTable — 空态与交互', () => {
  it('无数据时展示空态引导与三个入口', async () => {
    const { ctx, wrapper } = setup({ data: [] })

    expect(wrapper.find('.table-empty-title').text()).toBe('当前筛选下暂无测试点')
    const buttons = wrapper.findAll('.table-empty-actions .el-button')
    expect(buttons.map((b) => b.text())).toEqual(['从需求提取', '导入 XMind', '新增测试点'])

    for (const button of buttons) {
      await button.trigger('click')
    }

    expect(ctx.openExtractDialog).toHaveBeenCalledTimes(1)
    expect(ctx.openXmindImportDialog).toHaveBeenCalledTimes(1)
    expect(ctx.openCreateDialog).toHaveBeenCalledTimes(1)
  })

  it('表格选中与排序事件透传', () => {
    const { ctx, wrapper } = setup()

    const table = wrapper.findComponent(ElTableStub)
    table.vm.$emit('selection-change', [rows[0]])
    table.vm.$emit('sort-change', { prop: 'priority', order: 'ascending' })

    expect(ctx.handleSelectionChange).toHaveBeenCalledWith([rows[0]])
    expect(ctx.handleSortChange).toHaveBeenCalledWith({
      prop: 'priority',
      order: 'ascending',
    })
  })

  it('分页展示总数并转发翻页与页长事件', () => {
    const { ctx, wrapper } = setup()

    const pagination = wrapper.findComponent(ElPaginationStub)
    expect(pagination.attributes('data-total')).toBe('2')
    expect(pagination.attributes('data-page')).toBe('1')
    expect(pagination.attributes('data-size')).toBe('10')

    pagination.vm.$emit('current-change', 2)
    pagination.vm.$emit('size-change', 50)

    expect(ctx.fetchTestPoints).toHaveBeenCalledTimes(1)
    expect(ctx.handlePageSizeChange).toHaveBeenCalledTimes(1)
  })
})
