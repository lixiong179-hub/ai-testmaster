import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('../useTaskCreate', () => ({
  useTaskCreate: () => state.current,
}))

import TaskCreate from '../TaskCreate.vue'

const actions = {
  handleSelectionChange: vi.fn(),
  handleSelectAll: vi.fn(),
  clearSelection: vi.fn(),
  handleSearch: vi.fn(),
  handlePageChange: vi.fn(),
  submitForm: vi.fn(),
  resetForm: vi.fn(),
}

function makeCase(id: number, over: Record<string, unknown> = {}) {
  return {
    id,
    case_no: `CASE-00${id}`,
    module: '登录',
    title: `用例 ${id}`,
    priority: 1,
    case_type: 'web',
    ...over,
  }
}

function makeCtx(over: Record<string, unknown> = {}) {
  return {
    formRef: ref<unknown>(null),
    tableRef: ref<unknown>(null),
    loading: ref(false),
    submitting: ref(false),
    form: reactive({ task_name: '', description: '', case_ids: [11] as number[] }),
    filter: reactive({ module: '', priority: undefined as number | undefined, keyword: '' }),
    page: ref(1),
    pageSize: ref(10),
    total: ref(30),
    modules: ref(['登录', '订单']),
    filteredCases: ref([makeCase(11), makeCase(12, { priority: 2, case_type: null })]),
    selectAll: ref(false),
    rules: {},
    priorityText: (priority: number) => ({ 1: '高', 2: '中', 3: '低' })[priority] ?? '-',
    priorityType: (priority: number) => (priority === 1 ? 'danger' : 'info'),
    ...actions,
    ...over,
  }
}

let ctx: Record<string, unknown>

async function mountPage(over: Record<string, unknown> = {}) {
  ctx = makeCtx(over)
  state.current = ctx
  const wrapper = mount(TaskCreate)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('TaskCreate — 表单与用例列表', () => {
  it('渲染表单并完成表单/表格 ref 绑定', async () => {
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('创建测试任务')
    expect(wrapper.find('input[maxlength="100"]').exists()).toBe(true)
    expect((ctx.formRef as { value: unknown }).value).not.toBeNull()
    expect((ctx.tableRef as { value: unknown }).value).not.toBeNull()
  })

  it('用例表格渲染编号、模块、优先级与类型占位', async () => {
    const wrapper = await mountPage()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('CASE-0011')
    expect(rows[0].text()).toContain('登录')
    expect(rows[0].text()).toContain('高')
    // 类型为空时展示占位符
    expect(rows[1].text()).toContain('-')
  })

  it('已选数量跟随 case_ids 变化', async () => {
    const wrapper = await mountPage()

    expect(wrapper.find('.selection-info .count').text()).toBe('1')
    ;(ctx.form as { case_ids: number[] }).case_ids = [11, 12]
    await flushPromises()

    expect(wrapper.find('.selection-info .count').text()).toBe('2')
  })

  it('全选与清空选择透传动作', async () => {
    const wrapper = await mountPage()

    wrapper.findComponent({ name: 'ElCheckbox' }).vm.$emit('change', true)
    await flushPromises()
    const clearBtn = wrapper.findAll('.el-button').find((n) => n.text() === '清空选择')!
    await clearBtn.trigger('click')

    expect(actions.handleSelectAll).toHaveBeenCalledWith(true)
    expect(actions.clearSelection).toHaveBeenCalledTimes(1)
  })

  it('搜索框回车与按钮均触发查询', async () => {
    const wrapper = await mountPage()

    await wrapper.find('input[placeholder="搜索用例名称"]').trigger('keyup.enter')
    await wrapper.find('.case-filter .el-input-group__append .el-button').trigger('click')

    expect(actions.handleSearch).toHaveBeenCalledTimes(2)
  })

  it('总数大于当前页条数时展示分页并透传页码', async () => {
    const wrapper = await mountPage()

    const pager = wrapper.findComponent({ name: 'ElPagination' })
    expect(pager.exists()).toBe(true)

    pager.vm.$emit('current-change', 2)
    expect(actions.handlePageChange).toHaveBeenCalledWith(2)
  })

  it('数据不足一页时隐藏分页', async () => {
    const wrapper = await mountPage({ total: ref(2) })

    expect(wrapper.findComponent({ name: 'ElPagination' }).exists()).toBe(false)
  })
})

describe('TaskCreate — 提交', () => {
  it('创建任务与重置按钮透传动作', async () => {
    const wrapper = await mountPage()

    const submitBtn = wrapper.findAll('.el-button').find((n) => n.text().includes('创建任务'))!
    const resetBtn = wrapper.findAll('.el-button').find((n) => n.text().includes('重置'))!
    await submitBtn.trigger('click')
    await resetBtn.trigger('click')

    expect(actions.submitForm).toHaveBeenCalledTimes(1)
    expect(actions.resetForm).toHaveBeenCalledTimes(1)
  })

  it('提交中按钮进入 loading 态', async () => {
    const wrapper = await mountPage({ submitting: ref(true) })

    const submitBtn = wrapper.findAll('.el-button').find((n) => n.text().includes('创建任务'))!
    expect(submitBtn.classes()).toContain('is-loading')
  })

  it('取消与返回按钮调用路由返回', async () => {
    const back = vi.fn()
    ctx = makeCtx()
    state.current = ctx
    const wrapper = mount(TaskCreate, { global: { mocks: { $router: { back } } } })
    await flushPromises()

    await wrapper
      .findAll('.el-button')
      .find((n) => n.text() === '取消')!
      .trigger('click')
    await wrapper
      .findAll('.el-button')
      .find((n) => n.text().includes('返回'))!
      .trigger('click')

    expect(back).toHaveBeenCalledTimes(2)
  })
})
