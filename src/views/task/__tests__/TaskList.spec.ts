import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('../useTaskList', () => ({
  useTaskList: () => state.current,
}))

import TaskList from '../TaskList.vue'

const actions = {
  goToTestPointManagement: vi.fn(),
  createTask: vi.fn(),
  fetchTaskList: vi.fn(),
  viewTask: vi.fn(),
  handleRowClick: vi.fn(),
  startTask: vi.fn(),
  stopTask: vi.fn(),
  deleteTaskConfirm: vi.fn(),
  handleSizeChange: vi.fn(),
  handleCurrentChange: vi.fn(),
}

function makeTask(id: number, over: Record<string, unknown> = {}) {
  return {
    id,
    task_name: `任务 ${id}`,
    total_count: 20,
    success_count: 15,
    fail_count: 2,
    progress: 85,
    status: 0,
    create_time: '2026-11-16 08:00:00',
    ...over,
  }
}

function makeCtx(over: Record<string, unknown> = {}) {
  return {
    loading: ref(false),
    filter: reactive({ projectId: undefined as number | undefined, status: '' }),
    page: ref(1),
    pageSize: ref(10),
    total: ref(3),
    taskList: ref([
      makeTask(1, { status: 0 }),
      makeTask(2, { status: 1, progress: 40 }),
      makeTask(3, { status: 2, progress: 100, success_count: 20, fail_count: 0 }),
    ]),
    projectList: ref([
      { id: 7, name: 'Alpha 项目' },
      { id: 8, name: 'Beta 项目' },
    ]),
    isOverview: over.isOverview ?? false,
    taskStatusText: (status: number) =>
      ({ 0: '等待执行', 1: '执行中', 2: '执行完成' })[status] ?? '未知',
    taskStatusColor: () => 'primary',
    getProgressColor: (progress?: number) => (progress === 100 ? '#67c23a' : '#409eff'),
    getProgressStatus: (row: { status: number }) => (row.status === 1 ? undefined : 'success'),
    ...actions,
    ...over,
  }
}

let ctx: Record<string, unknown>

async function mountPage(over: Record<string, unknown> = {}) {
  ctx = makeCtx(over)
  state.current = ctx
  const wrapper = mount(TaskList)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('TaskList — 头部与筛选', () => {
  it('默认展示任务列表标题与说明', async () => {
    const wrapper = await mountPage()

    expect(wrapper.find('.card-title').text()).toBe('测试任务列表')
    expect(wrapper.text()).toContain('适合作为项目任务总览入口')
    expect(wrapper.find('.project-filter').exists()).toBe(false)
  })

  it('总览模式展示项目筛选与执行中心标题', async () => {
    const wrapper = await mountPage({ isOverview: true })

    expect(wrapper.find('.card-title').text()).toBe('执行中心')
    expect(wrapper.find('.project-filter').exists()).toBe(true)
  })

  it('项目筛选变化后重新拉取列表', async () => {
    const wrapper = await mountPage({ isOverview: true })

    wrapper.find('.project-filter').findComponent({ name: 'ElSelect' }).vm.$emit('change', 8)

    expect(actions.fetchTaskList).toHaveBeenCalled()
  })

  it('刷新按钮触发拉取并展示 loading 态', async () => {
    const wrapper = await mountPage({ loading: ref(true) })

    const refreshBtn = wrapper.findAll('.el-button').find((n) => n.text().includes('刷新'))!
    expect(refreshBtn.classes()).toContain('is-loading')
  })

  it('展示任务总数与创建/测试点管理入口', async () => {
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('共 3 条任务')

    await wrapper
      .findAll('.el-button')
      .find((n) => n.text() === '测试点管理')!
      .trigger('click')
    await wrapper
      .findAll('.el-button')
      .find((n) => n.text().includes('创建任务'))!
      .trigger('click')

    expect(actions.goToTestPointManagement).toHaveBeenCalledTimes(1)
    expect(actions.createTask).toHaveBeenCalledTimes(1)
  })
})

describe('TaskList — 表格与状态', () => {
  it('渲染任务行：名称、执行结果、进度与状态', async () => {
    const wrapper = await mountPage()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(3)
    expect(rows[0].text()).toContain('任务 1')
    expect(rows[0].find('.success-count').text()).toContain('15')
    expect(rows[0].find('.fail-count').text()).toContain('2')
    expect(rows[0].text()).toContain('等待执行')
    expect(rows[2].text()).toContain('执行完成')

    const progress = rows[2].findComponent({ name: 'ElProgress' })
    expect(progress.props('percentage')).toBe(100)
    expect(progress.props('color')).toBe('#67c23a')
  })

  it('点击行触发详情跳转', async () => {
    const wrapper = await mountPage()

    wrapper.findComponent({ name: 'ElTable' }).vm.$emit('row-click', makeTask(1))

    expect(actions.handleRowClick).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }))
  })

  it('按状态渲染启动/停止按钮', async () => {
    const wrapper = await mountPage()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows[0].findAll('.el-button').map((n) => n.text())).toEqual(['启动', '详情', '删除'])
    expect(rows[1].findAll('.el-button').map((n) => n.text())).toEqual(['停止', '详情', '删除'])

    await rows[0].findAll('.el-button')[0].trigger('click')
    await rows[1].findAll('.el-button')[0].trigger('click')
    expect(actions.startTask).toHaveBeenCalledTimes(1)
    expect(actions.stopTask).toHaveBeenCalledTimes(1)
  })

  it('运行中任务禁用删除，详情与删除各自透传', async () => {
    const wrapper = await mountPage()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows[1].findAll('.el-button')[2].attributes('disabled')).toBeDefined()
    expect(rows[0].findAll('.el-button')[2].attributes('disabled')).toBeUndefined()

    await rows[0].findAll('.el-button')[1].trigger('click')
    await rows[0].findAll('.el-button')[2].trigger('click')
    expect(actions.viewTask).toHaveBeenCalledTimes(1)
    expect(actions.deleteTaskConfirm).toHaveBeenCalledTimes(1)
  })

  it('空列表展示引导与创建首个任务入口', async () => {
    const wrapper = await mountPage({ taskList: ref([]), total: ref(0) })

    expect(wrapper.text()).toContain('当前项目还没有测试任务')
    await wrapper
      .findAll('.el-button')
      .find((n) => n.text().includes('创建首个任务'))!
      .trigger('click')
    await wrapper
      .findAll('.el-button')
      .find((n) => n.text().includes('先去测试点管理'))!
      .trigger('click')

    expect(actions.createTask).toHaveBeenCalledTimes(1)
    expect(actions.goToTestPointManagement).toHaveBeenCalledTimes(1)
  })
})

describe('TaskList — 分页', () => {
  it('有任务时展示分页并透传事件', async () => {
    const wrapper = await mountPage()

    const pager = wrapper.findComponent({ name: 'ElPagination' })
    expect(pager.exists()).toBe(true)

    pager.vm.$emit('size-change', 20)
    pager.vm.$emit('current-change', 2)

    expect(actions.handleSizeChange).toHaveBeenCalledWith(20)
    expect(actions.handleCurrentChange).toHaveBeenCalledWith(2)
  })

  it('无任务时隐藏分页', async () => {
    const wrapper = await mountPage({ taskList: ref([]), total: ref(0) })

    expect(wrapper.find('.pagination').exists()).toBe(false)
  })
})
