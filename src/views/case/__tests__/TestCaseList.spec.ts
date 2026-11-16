import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick, type Ref } from 'vue'

interface ListState {
  loading: Ref<boolean>
  exporting: Ref<boolean>
  projects: Ref<Array<{ id: number; name: string }>>
  selectedProjectId: Ref<number | undefined>
  testCases: Ref<Array<Record<string, unknown>>>
  total: Ref<number>
  page: Ref<number>
  pageSize: Ref<number>
  selectedRows: Ref<Array<Record<string, unknown>>>
  filters: Record<string, unknown>
  stats: Record<string, number>
}

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  handleProjectChange: vi.fn(),
  handleSelectionChange: vi.fn(),
  handleSortChange: vi.fn(),
  handlePageSizeChange: vi.fn(),
  resetFilters: vi.fn(),
  handleDelete: vi.fn(),
  handleBatchDelete: vi.fn(),
  handleBatchCreateTask: vi.fn(),
  handleBatchLocate: vi.fn(),
  handleQualityAnalysis: vi.fn(),
  fetchTestCases: vi.fn(),
  setBatchLocatorRef: vi.fn(),
  handleExportAll: vi.fn(),
  handleExportSelected: vi.fn(),
  state: {} as unknown as ListState,
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
}))

// 列表逻辑已有 useTestCaseList.spec.ts 覆盖，这里只验证页面模板与事件接线
vi.mock('../useTestCaseList', async () => {
  const { ref: createRef, reactive: createReactive } = await import('vue')
  const s = mocks.state
  s.loading = createRef(false)
  s.exporting = createRef(false)
  s.projects = createRef([{ id: 9, name: '项目A' }])
  s.selectedProjectId = createRef<number | undefined>(undefined)
  s.testCases = createRef<Array<Record<string, unknown>>>([])
  s.total = createRef(0)
  s.page = createRef(1)
  s.pageSize = createRef(20)
  s.selectedRows = createRef<Array<Record<string, unknown>>>([])
  s.filters = createReactive({
    keyword: '',
    module: '',
    priority: undefined,
    case_type: undefined,
    status: undefined,
    created_by: '',
    target_device: undefined,
    sort_by: 'create_time',
    sort_order: 'desc',
  })
  s.stats = createReactive({ total: 0, automated: 0, manual: 0, highPriority: 0 })

  return {
    useTestCaseList: () => ({
      loading: s.loading,
      projects: s.projects,
      selectedProjectId: s.selectedProjectId,
      testCases: s.testCases,
      total: s.total,
      page: s.page,
      pageSize: s.pageSize,
      selectedRows: s.selectedRows,
      filters: s.filters,
      stats: s.stats,
      exporting: s.exporting,
      handleProjectChange: mocks.handleProjectChange,
      handleSelectionChange: mocks.handleSelectionChange,
      handleSortChange: mocks.handleSortChange,
      handlePageSizeChange: mocks.handlePageSizeChange,
      resetFilters: mocks.resetFilters,
      handleDelete: mocks.handleDelete,
      handleBatchDelete: mocks.handleBatchDelete,
      handleBatchCreateTask: mocks.handleBatchCreateTask,
      handleBatchLocate: mocks.handleBatchLocate,
      handleQualityAnalysis: mocks.handleQualityAnalysis,
      fetchTestCases: mocks.fetchTestCases,
      setBatchLocatorRef: mocks.setBatchLocatorRef,
      handleExportAll: mocks.handleExportAll,
      handleExportSelected: mocks.handleExportSelected,
      getPriorityType: (p: number) => (p === 1 ? 'danger' : p === 2 ? 'warning' : 'info'),
      getPriorityLabel: (p: number) => (p === 1 ? '高' : p === 2 ? '中' : '低'),
      getTypeLabel: (t: string) =>
        t === 'ui_automation' ? 'UI自动化' : t === 'manual' ? '手工测试' : 'API自动化',
      getTypeTagType: (t: string) =>
        t === 'ui_automation' ? 'success' : t === 'manual' ? 'info' : 'primary',
    }),
  }
})

import TestCaseList from '../TestCaseList.vue'

const state = mocks.state

function makeCase(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    module: '登录',
    title: '账号密码登录',
    priority: 1,
    case_type: 'ui_automation',
    status: 'draft',
    created_by: '张三',
    create_time: '2026-06-27 10:00:00',
    ...overrides,
  }
}

async function mountPage() {
  const wrapper = mount(TestCaseList, {
    global: {
      mocks: { $router: { push: mocks.push } },
      stubs: { BatchLocatorDialog: true },
    },
  })
  // el-table 的表格体在挂载后异步渲染，需要先排空微任务再断言行内容
  await flushPromises()
  return wrapper
}

function findButton(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper.findAll('button').find((btn) => btn.text().includes(text))
}

beforeEach(() => {
  vi.clearAllMocks()
  state.loading.value = false
  state.exporting.value = false
  state.selectedProjectId.value = undefined
  state.testCases.value = []
  state.total.value = 0
  state.page.value = 1
  state.pageSize.value = 20
  state.selectedRows.value = []
  state.stats.total = 0
  state.stats.automated = 0
  state.stats.manual = 0
  state.stats.highPriority = 0
})

describe('TestCaseList — 空态与统计', () => {
  it('未选项目时展示空态，不渲染工作区', async () => {
    const wrapper = await mountPage()

    expect(wrapper.find('.el-empty').text()).toContain('请选择项目后查看用例列表')
    expect(wrapper.find('.workspace-card').exists()).toBe(false)
  })

  it('选中项目后渲染统计卡片', async () => {
    state.selectedProjectId.value = 9
    state.stats.total = 40
    state.stats.automated = 25
    state.stats.manual = 15
    state.stats.highPriority = 8
    const wrapper = await mountPage()

    const chips = wrapper.findAll('.stat-chip')
    expect(chips).toHaveLength(4)
    expect(chips[0].text()).toContain('总计')
    expect(chips[0].text()).toContain('40')
    expect(chips[1].text()).toContain('25')
    expect(chips[2].text()).toContain('15')
    expect(chips[3].text()).toContain('8')
  })
})

describe('TestCaseList — 表格渲染', () => {
  it('按行渲染模块、名称、状态、创建人与时间', async () => {
    state.selectedProjectId.value = 9
    state.testCases.value = [makeCase()]
    const wrapper = await mountPage()

    const row = wrapper.find('.el-table__row')
    expect(row.text()).toContain('登录')
    expect(row.text()).toContain('账号密码登录')
    expect(row.text()).toContain('draft')
    expect(row.text()).toContain('张三')
    expect(row.text()).toContain('2026-06-27 10:00:00')
  })

  it('优先级与类型标签使用对应文案与颜色', async () => {
    state.selectedProjectId.value = 9
    state.testCases.value = [
      makeCase({ priority: 1, case_type: 'ui_automation' }),
      makeCase({ id: 2, priority: 2, case_type: 'manual' }),
      makeCase({ id: 3, priority: 3, case_type: 'api_automation' }),
    ]
    const wrapper = await mountPage()

    const rows = wrapper.findAll('.el-table__row')
    const tagsOf = (index: number) => rows[index].findAll('.el-tag')

    expect(tagsOf(0)[0].text()).toBe('高')
    expect(tagsOf(0)[0].classes().join(' ')).toMatch(/danger/)
    expect(tagsOf(1)[0].text()).toBe('中')
    expect(tagsOf(1)[0].classes().join(' ')).toMatch(/warning/)
    expect(tagsOf(2)[0].text()).toBe('低')
    expect(tagsOf(2)[0].classes().join(' ')).toMatch(/info/)

    expect(tagsOf(0)[1].text()).toBe('UI自动化')
    expect(tagsOf(1)[1].text()).toBe('手工测试')
    expect(tagsOf(2)[1].text()).toBe('API自动化')
  })

  it('行内操作按钮齐全', async () => {
    state.selectedProjectId.value = 9
    state.testCases.value = [makeCase()]
    const wrapper = await mountPage()

    const texts = wrapper
      .find('.el-table__row')
      .findAll('button')
      .map((btn) => btn.text())
    expect(texts).toEqual(['查看', '质量分析', '删除'])
  })

  it('点击行内操作分别派发查看、质量分析与删除', async () => {
    state.selectedProjectId.value = 9
    state.testCases.value = [makeCase()]
    const wrapper = await mountPage()
    const row = wrapper.find('.el-table__row')

    await row.findAll('button')[0].trigger('click')
    expect(mocks.push).toHaveBeenCalledWith('/home/case/detail/1')

    await row.findAll('button')[1].trigger('click')
    expect(mocks.handleQualityAnalysis).toHaveBeenCalledTimes(1)

    await row.findAll('button')[2].trigger('click')
    expect(mocks.handleDelete).toHaveBeenCalledTimes(1)
  })
})

describe('TestCaseList — 筛选与分页', () => {
  it('关键字回车触发查询', async () => {
    state.selectedProjectId.value = 9
    const wrapper = await mountPage()

    await wrapper.find('input[placeholder="搜索用例名称"]').trigger('keyup.enter')

    expect(mocks.fetchTestCases).toHaveBeenCalledTimes(1)
  })

  it('查询与重置按钮分别触发拉取与重置', async () => {
    state.selectedProjectId.value = 9
    const wrapper = await mountPage()

    await findButton(wrapper, '查询')!.trigger('click')
    expect(mocks.fetchTestCases).toHaveBeenCalledTimes(1)

    await findButton(wrapper, '重置')!.trigger('click')
    expect(mocks.resetFilters).toHaveBeenCalledTimes(1)
  })

  it.each(['优先级', '用例类型', '状态', '设备类型'])(
    '「%s」筛选变化后重新拉取',
    async (placeholder) => {
      state.selectedProjectId.value = 9
      const wrapper = await mountPage()
      const select = wrapper
        .findAllComponents({ name: 'ElSelect' })
        .find((item) => item.props('placeholder') === placeholder)

      select!.vm.$emit('change', 'x')
      await nextTick()

      expect(mocks.fetchTestCases).toHaveBeenCalledTimes(1)
    }
  )

  it('切换分页与每页条数触发对应处理器', async () => {
    state.selectedProjectId.value = 9
    const wrapper = await mountPage()
    const pagination = wrapper.findComponent({ name: 'ElPagination' })

    pagination.vm.$emit('current-change', 2)
    pagination.vm.$emit('size-change', 50)
    await nextTick()

    expect(mocks.fetchTestCases).toHaveBeenCalledTimes(1)
    expect(mocks.handlePageSizeChange).toHaveBeenCalledWith(50)
  })

  it('表格排序事件透传给处理器', async () => {
    state.selectedProjectId.value = 9
    const wrapper = await mountPage()

    wrapper
      .findComponent({ name: 'ElTable' })
      .vm.$emit('sort-change', { prop: 'priority', order: 'ascending' })
    await nextTick()

    expect(mocks.handleSortChange).toHaveBeenCalledWith({
      prop: 'priority',
      order: 'ascending',
    })
  })
})

describe('TestCaseList — 批量操作条', () => {
  it('未选中行时不展示批量操作条', async () => {
    state.selectedProjectId.value = 9
    const wrapper = await mountPage()

    expect(wrapper.find('.batch-bar').exists()).toBe(false)
  })

  it('选中行后展示数量与三个批量按钮', async () => {
    state.selectedProjectId.value = 9
    state.selectedRows.value = [makeCase(), makeCase({ id: 2 })]
    const wrapper = await mountPage()

    const bar = wrapper.find('.batch-bar')
    expect(bar.text()).toContain('已选 2 条')
    expect(bar.findAll('button').map((btn) => btn.text())).toEqual([
      '创建任务',
      '批量元素定位',
      '批量删除',
    ])
  })

  it('批量按钮分别触发对应处理器', async () => {
    state.selectedProjectId.value = 9
    state.selectedRows.value = [makeCase()]
    const wrapper = await mountPage()
    const buttons = wrapper.find('.batch-bar').findAll('button')

    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    await buttons[2].trigger('click')

    expect(mocks.handleBatchCreateTask).toHaveBeenCalledTimes(1)
    expect(mocks.handleBatchLocate).toHaveBeenCalledTimes(1)
    expect(mocks.handleBatchDelete).toHaveBeenCalledTimes(1)
  })
})

describe('TestCaseList — 导航与联动', () => {
  it('顶部按钮跳转迁移与保鲜建议页', async () => {
    const wrapper = await mountPage()

    await findButton(wrapper, '用例迁移')!.trigger('click')
    expect(mocks.push).toHaveBeenCalledWith('/home/case/migration')

    await findButton(wrapper, '保鲜建议')!.trigger('click')
    expect(mocks.push).toHaveBeenCalledWith('/home/case/case-refresh')
  })

  it('挂载后把批量定位弹窗实例注入组合式函数', async () => {
    await mountPage()

    expect(mocks.setBatchLocatorRef).toHaveBeenCalledTimes(1)
    expect(mocks.setBatchLocatorRef.mock.calls[0][0]).toBeTruthy()
  })

  it('导出按钮展示加载态', async () => {
    state.selectedProjectId.value = 9
    state.exporting.value = true
    const wrapper = await mountPage()

    const exportBtn = wrapper
      .findAllComponents({ name: 'ElButton' })
      .find((btn) => btn.text().includes('导出'))
    expect(exportBtn!.props('loading')).toBe(true)
  })
})
