import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, nextTick, reactive, ref } from 'vue'

const listState = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))
const quickState = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('../useProjectList', () => ({
  useProjectList: () => listState.current,
}))

vi.mock('../useQuickTestEntry', () => ({
  useQuickTestCard: () => quickState.current,
}))

import ProjectListPage from '../ProjectList.vue'

const handlers = {
  handleSearch: vi.fn(),
  handleCurrentChange: vi.fn(),
  handleSizeChange: vi.fn(),
  openCreateDialog: vi.fn(),
  createProject: vi.fn(),
  goToDetail: vi.fn(),
  goToTaskList: vi.fn(),
  goToTestPointManagement: vi.fn(),
  confirmDelete: vi.fn(),
}

const quickHandlers = {
  clearError: vi.fn(),
  submitCard: vi.fn(),
}

/** el-dialog 依赖 teleport/过渡，happy-dom 下不渲染内容，改用按 modelValue 渲染插槽的桩 */
const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: `<div class="el-dialog" v-if="modelValue" :data-title="title">
    <div class="el-dialog__body"><slot /></div>
    <div class="el-dialog__footer"><slot name="footer" /></div>
  </div>`,
})

const stubs = { ElDialog: ElDialogStub }

function makeProject(id: number, over: Record<string, unknown> = {}) {
  return {
    id,
    name: `项目 ${id}`,
    project_type: 'web',
    source: 'manual',
    description: `描述 ${id}`,
    status: 1,
    create_time: '2026-11-16 08:00:00',
    ...over,
  }
}

function makeEnvConfig() {
  return {
    test: { url: '', username: '', password: '' },
    staging: { url: '', username: '', password: '' },
    prod: { url: '', username: '', password: '' },
  }
}

function makeListCtx(over: Record<string, unknown> = {}) {
  return {
    projectStore: reactive({
      projects: [makeProject(1), makeProject(2, { project_type: 'app', status: 2 })],
      total: 5,
      loading: false,
      currentPage: 1,
      pageSize: 10,
    }),
    dialogVisible: ref(false),
    projectFormRef: ref<unknown>(null),
    searchKeyword: ref(''),
    sourceFilter: ref(''),
    projectForm: reactive({
      name: '',
      project_type: 'web',
      description: '',
      web_env_configs: makeEnvConfig(),
    }),
    projectRules: {},
    filteredProjects: ref([
      makeProject(1),
      makeProject(2, { project_type: 'app', status: 2, source: 'url_quick_test' }),
    ]),
    getSourceTagType: (source?: string) => (source === 'url_quick_test' ? 'primary' : 'info'),
    getSourceText: (source?: string) => (source === 'url_quick_test' ? '快速测试' : '手动创建'),
    getStatusType: () => 'success',
    getStatusText: (status: number) => (status === 2 ? '归档' : '正常'),
    ...handlers,
    ...over,
  }
}

function makeQuickCtx(over: Record<string, unknown> = {}) {
  return {
    url: ref(''),
    description: ref(''),
    username: ref(''),
    password: ref(''),
    error: ref(''),
    loading: ref(false),
    ...quickHandlers,
    ...over,
  }
}

let listCtx: Record<string, unknown>
let quickCtx: Record<string, unknown>

function mountPage(
  listOver: Record<string, unknown> = {},
  quickOver: Record<string, unknown> = {}
) {
  listCtx = makeListCtx(listOver)
  quickCtx = makeQuickCtx(quickOver)
  listState.current = listCtx
  quickState.current = quickCtx
  return mount(ProjectListPage, { global: { stubs } })
}

async function mountAndFlush(
  listOver: Record<string, unknown> = {},
  quickOver: Record<string, unknown> = {}
) {
  const wrapper = mountPage(listOver, quickOver)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ProjectList — 快速测试卡片', () => {
  it('输入网址并点击开始测试触发提交', async () => {
    const wrapper = await mountAndFlush()

    await wrapper.find('.quick-test-url-input input').setValue('https://example.com')
    const submitBtn = wrapper
      .findAll('.quick-test-actions .el-button')
      .find((node) => node.text().includes('开始测试'))!
    await submitBtn.trigger('click')

    expect((quickCtx.url as { value: string }).value).toBe('https://example.com')
    expect(quickHandlers.submitCard).toHaveBeenCalledTimes(1)
  })

  it('回车提交快速测试', async () => {
    const wrapper = await mountAndFlush()

    await wrapper.find('.quick-test-url-input input').trigger('keyup.enter')

    expect(quickHandlers.submitCard).toHaveBeenCalledTimes(1)
  })

  it('错误提示渲染并随输入清除', async () => {
    const wrapper = await mountAndFlush({}, { error: ref('请输入网址') })

    expect(wrapper.find('.quick-test-error').text()).toBe('请输入网址')

    // `@input` 声明在 el-input 组件上，直接向组件派发事件
    wrapper.findAllComponents({ name: 'ElInput' })[0].vm.$emit('input', 'https://example.com')
    await nextTick()

    expect(quickHandlers.clearError).toHaveBeenCalledTimes(1)
  })

  it('提交中按钮展示 loading 态', async () => {
    const wrapper = await mountAndFlush({}, { loading: ref(true) })

    const submitBtn = wrapper
      .findAll('.quick-test-actions .el-button')
      .find((node) => node.text().includes('开始测试'))!
    expect(submitBtn.classes()).toContain('is-loading')
  })
})

describe('ProjectList — 项目表格', () => {
  it('渲染项目行：名称链接、类型、来源、状态与描述', async () => {
    const wrapper = await mountAndFlush()

    const rows = wrapper.findAll('.project-table .el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('项目 1')
    expect(rows[0].text()).toContain('Web端')
    expect(rows[0].text()).toContain('手动创建')
    expect(rows[1].text()).toContain('C端')
    expect(rows[1].text()).toContain('快速测试')
    expect(rows[1].text()).toContain('归档')
  })

  it('点击项目名进入详情', async () => {
    const wrapper = await mountAndFlush()

    await wrapper.find('.project-table .el-link').trigger('click')

    expect(handlers.goToDetail).toHaveBeenCalledWith(1)
  })

  it('行内操作按钮分别触发详情/任务/测试点/删除', async () => {
    const wrapper = await mountAndFlush()

    const buttons = wrapper.findAll('.project-table .el-table__row')[0].findAll('.el-button')
    const byText = (text: string) => buttons.find((node) => node.text() === text)!

    await byText('详情').trigger('click')
    await byText('任务').trigger('click')
    await byText('测试点').trigger('click')
    await byText('删除').trigger('click')

    expect(handlers.goToDetail).toHaveBeenCalledWith(1)
    expect(handlers.goToTaskList).toHaveBeenCalledWith(1)
    expect(handlers.goToTestPointManagement).toHaveBeenCalledWith(1)
    expect(handlers.confirmDelete).toHaveBeenCalledWith(1)
  })

  it('展示项目总数', async () => {
    const wrapper = await mountAndFlush()

    expect(wrapper.text()).toContain('共 5 个项目')
  })

  it('空列表渲染引导文案与创建入口', async () => {
    const wrapper = await mountAndFlush({
      filteredProjects: ref([]),
      projectStore: reactive({ total: 0, loading: false, currentPage: 1, pageSize: 10 }),
    })

    expect(wrapper.find('.project-empty-title').text()).toBe('还没有可用项目')
    const createFirst = wrapper
      .findAll('.project-empty-state .el-button')
      .find((node) => node.text().includes('创建首个项目'))!
    await createFirst.trigger('click')

    expect(handlers.openCreateDialog).toHaveBeenCalledTimes(1)
  })
})

describe('ProjectList — 查询与分页', () => {
  it('搜索框回车与搜索按钮都触发查询', async () => {
    const wrapper = await mountAndFlush()

    await wrapper.find('.search-input input').trigger('keyup.enter')
    const searchBtn = wrapper
      .findAll('.search-input .el-button')
      .find((node) => node.text() === '搜索')!
    await searchBtn.trigger('click')

    expect(handlers.handleSearch).toHaveBeenCalledTimes(2)
  })

  it('分页事件透传页码与页大小', async () => {
    const wrapper = await mountAndFlush()

    const pager = wrapper.findComponent({ name: 'ElPagination' })
    pager.vm.$emit('size-change', 20)
    pager.vm.$emit('current-change', 2)

    expect(handlers.handleSizeChange).toHaveBeenCalledWith(20)
    expect(handlers.handleCurrentChange).toHaveBeenCalledWith(2)
  })
})

describe('ProjectList — 创建项目弹窗', () => {
  it('header 按钮打开创建弹窗', async () => {
    const wrapper = await mountAndFlush()

    const createBtn = wrapper
      .findAll('.project-card .el-button')
      .find((node) => node.text().includes('创建项目'))!
    await createBtn.trigger('click')

    expect(handlers.openCreateDialog).toHaveBeenCalledTimes(1)
  })

  it('弹窗确定触发创建、取消关闭弹窗', async () => {
    const wrapper = await mountAndFlush({ dialogVisible: ref(true) })

    const footerButtons = wrapper.findAll('.dialog-footer .el-button')
    await footerButtons[0].trigger('click')
    expect((listCtx.dialogVisible as { value: boolean }).value).toBe(false)
    ;(listCtx.dialogVisible as { value: boolean }).value = true
    await nextTick()
    const confirmBtn = wrapper
      .findAll('.dialog-footer .el-button')
      .find((node) => node.text() === '确定')!
    await confirmBtn.trigger('click')

    expect(handlers.createProject).toHaveBeenCalledTimes(1)
  })

  it('web 类型展示多环境配置，app 类型展示预留提示', async () => {
    const wrapper = await mountAndFlush({ dialogVisible: ref(true) })

    expect(wrapper.text()).toContain('Web端多环境配置（选填）')
    expect(wrapper.text()).not.toContain('C端测试功能正在开发中')
    ;(listCtx.projectForm as { project_type: string }).project_type = 'app'
    await nextTick()

    expect(wrapper.text()).toContain('C端测试功能正在开发中')
  })
})
