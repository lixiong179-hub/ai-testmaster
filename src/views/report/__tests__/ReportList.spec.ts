import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { mockCancel, mockConfirm, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  getProjects: vi.fn(),
  fetchReports: vi.fn(),
  exportReportPDF: vi.fn(),
  exportReportHTML: vi.fn(),
  deleteReport: vi.fn(),
  routeQuery: { project_id: undefined as string | undefined },
  reports: [] as Record<string, unknown>[],
  total: 0,
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
  useRoute: () => ({ query: mocks.routeQuery }),
}))

vi.mock('@/store/report', () => ({
  useReportStore: () =>
    reactive({
      reports: mocks.reports,
      total: mocks.total,
      fetchReports: mocks.fetchReports,
      exportReportPDF: mocks.exportReportPDF,
      exportReportHTML: mocks.exportReportHTML,
      deleteReport: mocks.deleteReport,
    }),
}))

vi.mock('@/api/project', () => ({
  default: { getProjects: mocks.getProjects },
}))

import ReportListPage from '../ReportList.vue'

const ElDropdownStub = defineComponent({
  name: 'ElDropdown',
  template: '<div class="el-dropdown"><slot /><slot name="dropdown" /></div>',
})
const ElDropdownMenuStub = defineComponent({
  name: 'ElDropdownMenu',
  template: '<div class="el-dropdown-menu"><slot /></div>',
})
const ElDropdownItemStub = defineComponent({
  name: 'ElDropdownItem',
  emits: ['click'],
  template: '<div class="el-dropdown-item" @click="$emit(\'click\')"><slot /></div>',
})

const stubs = {
  ElDropdown: ElDropdownStub,
  ElDropdownMenu: ElDropdownMenuStub,
  ElDropdownItem: ElDropdownItemStub,
}

function makeReport(id: number, over: Record<string, unknown> = {}) {
  return {
    id,
    name: `报告 ${id}`,
    project_id: 7,
    total_cases: 20,
    passed_cases: 15,
    failed_cases: 3,
    blocked_cases: 2,
    pass_rate: 75,
    create_time: '2026-11-16 08:00:00',
    ...over,
  }
}

async function mountPage(over: { reports?: Record<string, unknown>[]; total?: number } = {}) {
  mocks.reports.splice(0, mocks.reports.length, ...(over.reports ?? [makeReport(1), makeReport(2)]))
  mocks.total = over.total ?? 2
  const wrapper = mount(ReportListPage, { global: { stubs } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mockConfirm()
  mocks.routeQuery = { project_id: undefined }
  mocks.getProjects.mockResolvedValue({
    data: { items: [{ id: 7, name: 'Alpha 项目' }] },
  })
  mocks.fetchReports.mockResolvedValue(undefined)
  mocks.exportReportPDF.mockResolvedValue({ data: new Uint8Array([1, 2]) })
  mocks.exportReportHTML.mockResolvedValue({ data: '<html></html>' })
  mocks.deleteReport.mockResolvedValue(undefined)
  URL.createObjectURL = vi.fn(() => 'blob:mock')
  URL.revokeObjectURL = vi.fn()
})

describe('ReportList — 初始化加载', () => {
  it('挂载后加载项目与报告列表', async () => {
    await mountPage()

    expect(mocks.getProjects).toHaveBeenCalledWith({ page: 1, page_size: 100 })
    expect(mocks.fetchReports).toHaveBeenCalledWith({
      page: 1,
      page_size: 10,
      project_id: undefined,
    })
  })

  it('项目加载失败时提示', async () => {
    mocks.getProjects.mockRejectedValue(new Error('boom'))

    await mountPage()

    expect(ElMessage.error).toHaveBeenCalledWith('获取项目列表失败')
  })

  it('报告加载失败时提示', async () => {
    mocks.fetchReports.mockRejectedValue(new Error('boom'))

    await mountPage()

    expect(ElMessage.error).toHaveBeenCalledWith('获取报告列表失败')
  })

  it('URL 带 project_id 时作为默认筛选值', async () => {
    mocks.routeQuery = { project_id: '7' }
    const wrapper = await mountPage()
    mocks.fetchReports.mockClear()

    const queryBtn = wrapper.findAll('.el-button').find((node) => node.text() === '查询')!
    await queryBtn.trigger('click')
    await flushPromises()

    expect(mocks.fetchReports).toHaveBeenCalledWith(expect.objectContaining({ project_id: 7 }))
  })
})

describe('ReportList — 表格与分页', () => {
  it('渲染报告行并通过率保留两位小数', async () => {
    const wrapper = await mountPage({
      reports: [makeReport(1, { pass_rate: 75 }), makeReport(2, { pass_rate: 66.666 })],
    })

    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('报告 1')
    expect(rows[0].text()).toContain('75.00%')
    expect(rows[1].text()).toContain('66.67%')
  })

  it('总数大于 0 时展示分页', async () => {
    const wrapper = await mountPage({ total: 12 })

    expect(wrapper.find('.pagination').exists()).toBe(true)
  })

  it('无数据时隐藏分页', async () => {
    const wrapper = await mountPage({ reports: [], total: 0 })

    expect(wrapper.find('.pagination').exists()).toBe(false)
  })

  it('切换页大小与页码重新查询', async () => {
    const wrapper = await mountPage({ total: 12 })
    mocks.fetchReports.mockClear()

    const pager = wrapper.findComponent({ name: 'ElPagination' })
    pager.vm.$emit('size-change', 20)
    await flushPromises()
    pager.vm.$emit('current-change', 3)
    await flushPromises()

    expect(mocks.fetchReports).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ page: 1, page_size: 20 })
    )
    expect(mocks.fetchReports).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ page: 3, page_size: 20 })
    )
  })
})

describe('ReportList — 查看与导出', () => {
  it('查看报告跳转详情页', async () => {
    const wrapper = await mountPage()

    const viewBtn = wrapper.findAll('.el-table__row')[0].findAll('.el-button')[0]
    await viewBtn.trigger('click')

    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/report/detail',
      query: { id: 1, project_id: 7 },
    })
  })

  it('缺少项目 ID 时查看与导出都被拦截', async () => {
    const wrapper = await mountPage({ reports: [makeReport(1, { project_id: null })] })

    const row = wrapper.findAll('.el-table__row')[0]
    await row.findAll('.el-button')[0].trigger('click')

    expect(ElMessage.error).toHaveBeenCalledWith('报告缺少项目ID，无法查看详情')
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('导出 PDF 成功触发下载', async () => {
    const wrapper = await mountPage()

    const exportItem = wrapper
      .findAll('.el-dropdown-item')
      .find((node) => node.text() === '导出PDF')!
    await exportItem.trigger('click')
    await flushPromises()

    expect(mocks.exportReportPDF).toHaveBeenCalledWith(1, 7)
    expect(ElMessage.success).toHaveBeenCalledWith('导出PDF成功')
  })

  it('导出 HTML 成功触发下载', async () => {
    const wrapper = await mountPage()

    const exportItem = wrapper
      .findAll('.el-dropdown-item')
      .find((node) => node.text() === '导出HTML')!
    await exportItem.trigger('click')
    await flushPromises()

    expect(mocks.exportReportHTML).toHaveBeenCalledWith(1, 7)
    expect(ElMessage.success).toHaveBeenCalledWith('导出HTML成功')
  })

  it('导出失败时提示', async () => {
    mocks.exportReportPDF.mockRejectedValue(new Error('boom'))
    const wrapper = await mountPage()

    const exportItem = wrapper
      .findAll('.el-dropdown-item')
      .find((node) => node.text() === '导出PDF')!
    await exportItem.trigger('click')
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('导出PDF失败')
  })
})

describe('ReportList — 删除', () => {
  it('确认后删除报告', async () => {
    const wrapper = await mountPage()

    const row = wrapper.findAll('.el-table__row')[0]
    const deleteBtn = row.findAll('.el-button').find((node) => node.text() === '删除')!
    await deleteBtn.trigger('click')
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(mocks.deleteReport).toHaveBeenCalledWith(1, 7)
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
  })

  it('取消删除时不调用接口', async () => {
    mockCancel()
    const wrapper = await mountPage()

    const row = wrapper.findAll('.el-table__row')[0]
    await row
      .findAll('.el-button')
      .find((node) => node.text() === '删除')!
      .trigger('click')
    await flushPromises()

    expect(mocks.deleteReport).not.toHaveBeenCalled()
  })

  it('删除失败时提示', async () => {
    mocks.deleteReport.mockRejectedValue(new Error('boom'))
    const wrapper = await mountPage()

    const row = wrapper.findAll('.el-table__row')[0]
    await row
      .findAll('.el-button')
      .find((node) => node.text() === '删除')!
      .trigger('click')
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })

  it('缺少项目 ID 时拒绝删除', async () => {
    const wrapper = await mountPage({ reports: [makeReport(1, { project_id: null })] })

    const row = wrapper.findAll('.el-table__row')[0]
    await row
      .findAll('.el-button')
      .find((node) => node.text() === '删除')!
      .trigger('click')

    expect(ElMessage.error).toHaveBeenCalledWith('报告缺少项目ID，无法删除')
    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
  })
})
