import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createComposableHost,
  deferred,
  mockConfirm,
  silenceConsole,
  silenceElMessage,
} from '@/test-utils'

const mocks = vi.hoisted(() => ({
  route: { query: {} as Record<string, string> },
  push: vi.fn(),
  getProjects: vi.fn(),
  getFileListByProject: vi.fn(),
  extract: vi.fn(),
  getList: vi.fn(),
  batchSave: vi.fn(),
  update: vi.fn(),
  delete: vi.fn(),
  batchDelete: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/api/project', () => ({
  default: { getProjects: mocks.getProjects },
}))

vi.mock('@/api/file', () => {
  const api = { getFileListByProject: mocks.getFileListByProject }
  return { fileApi: api, default: api }
})

vi.mock('@/api/testPoint', () => {
  const api = {
    extract: mocks.extract,
    getList: mocks.getList,
    batchSave: mocks.batchSave,
    update: mocks.update,
    delete: mocks.delete,
    batchDelete: mocks.batchDelete,
  }
  return { testPointApi: api, default: api }
})

import { provideTestPointExtract, useTestPointExtract } from '../index'

type Ctx = ReturnType<typeof provideTestPointExtract>

let ctx: Ctx

const host = createComposableHost(() => provideTestPointExtract())

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

const file = {
  id: 3,
  project_id: 7,
  file_name: '需求.pdf',
  file_url: 'u',
  file_type: 'pdf',
  size: 2048,
  upload_time: '2026-11-13',
  file_source: 'upload',
  resource_type: 'requirement',
}

function makePoint(overrides: Record<string, unknown> = {}) {
  return { id: 1, module: '模块A', point: '测试点', priority: 1, ...overrides }
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.route.query = {}
  silenceElMessage()
  mockConfirm()
  silenceConsole('error')

  mocks.getProjects.mockResolvedValue({
    data: {
      items: [
        { id: 7, name: '项目A' },
        { id: 8, name: '默认项目' },
      ],
    },
  })
  mocks.getFileListByProject.mockResolvedValue({ data: { items: [file] } })
  mocks.extract.mockResolvedValue({ items: [{ module: '模块A', point: '点1', priority: 1 }] })
  mocks.getList.mockResolvedValue({
    items: [makePoint()],
    total: 1,
  })
  mocks.batchSave.mockResolvedValue({ code: 200, message: '保存成功' })
  mocks.update.mockResolvedValue({ code: 200, data: makePoint({ point: '新点' }) })
  mocks.delete.mockResolvedValue({ code: 200 })
  mocks.batchDelete.mockResolvedValue({ code: 200, data: { deleted_count: 2 } })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('testPointExtract — 项目与资源', () => {
  it('加载项目列表并过滤默认项目', async () => {
    await mountHost()

    await ctx.getProjects()

    expect(mocks.getProjects).toHaveBeenCalledWith({})
    expect(ctx.projects.value).toEqual([{ id: 7, name: '项目A' }])
  })

  it('项目接口无数据时置空', async () => {
    mocks.getProjects.mockResolvedValue({})
    await mountHost()

    await ctx.getProjects()

    expect(ctx.projects.value).toEqual([])
  })

  it('项目接口异常时置空并记录日志', async () => {
    mocks.getProjects.mockRejectedValue(new Error('boom'))
    await mountHost()

    await ctx.getProjects()

    expect(console.error).toHaveBeenCalled()
    expect(ctx.projects.value).toEqual([])
  })

  it('加载资源列表并映射为表格行', async () => {
    await mountHost()

    await ctx.loadResources(7)

    expect(mocks.getFileListByProject).toHaveBeenCalledWith(7)
    expect(ctx.files.value).toHaveLength(1)
    expect(ctx.resourceRows.value[0]).toEqual({
      source: 'file',
      id: 3,
      project_id: 7,
      display_name: '需求.pdf',
      resource_type: 'requirement',
      type_label: '需求文档',
      size_text: '2.00 KB',
      time_text: '2026-11-13',
    })
  })

  it('资源接口无 items 与异常时都置空', async () => {
    mocks.getFileListByProject.mockResolvedValueOnce({})
    await mountHost()
    await ctx.loadResources(7)
    expect(ctx.files.value).toEqual([])

    mocks.getFileListByProject.mockRejectedValueOnce(new Error('boom'))
    await ctx.loadResources(7)
    expect(ctx.files.value).toEqual([])
    expect(console.error).toHaveBeenCalled()
  })

  it('资源类型过滤生效', async () => {
    mocks.getFileListByProject.mockResolvedValue({
      data: {
        items: [
          file,
          { ...file, id: 4, file_name: '原型.png', resource_type: 'ui_mockup', size: 1024 * 1024 },
        ],
      },
    })
    await mountHost()
    await ctx.loadResources(7)

    expect(ctx.filteredResourceRows.value).toHaveLength(2)

    ctx.resourceTypeFilter.value = 'ui_mockup'
    expect(ctx.filteredResourceRows.value).toHaveLength(1)
    expect(ctx.filteredResourceRows.value[0].display_name).toBe('原型.png')
  })

  it('文件大小与类型辅助函数', async () => {
    await mountHost()

    expect(ctx.formatFileSize(512)).toBe('512 B')
    expect(ctx.formatFileSize(2048)).toBe('2.00 KB')
    expect(ctx.formatFileSize(2 * 1024 * 1024)).toBe('2.00 MB')

    expect(ctx.getResourceTypeLabel('api_doc')).toBe('API文档')
    expect(ctx.getResourceTypeLabel('custom')).toBe('custom')
    expect(ctx.getResourceTypeTagType('ui_mockup')).toBe('warning')
    expect(ctx.getResourceTypeTagType('custom')).toBe('info')
    expect(ctx.getResourceIcon('test_data')).toBe('Files')
    expect(ctx.getResourceIcon('custom')).toBe('Document')
  })

  it('类型数量与占比统计', async () => {
    mocks.getFileListByProject.mockResolvedValue({
      data: {
        items: [
          file,
          { ...file, id: 4, resource_type: 'requirement' },
          { ...file, id: 5, resource_type: 'ui_mockup' },
          { ...file, id: 6, resource_type: 'ui_mockup' },
        ],
      },
    })
    await mountHost()
    await ctx.loadResources(7)

    expect(ctx.getResourceTypeCount('requirement')).toBe(2)
    expect(ctx.getResourceTypePercentage('requirement')).toBe(50)
    expect(ctx.getResourceTypePercentage('other')).toBe(0)
  })

  it('未选择项目时占比为 0 且项目信息为空', async () => {
    await mountHost()

    expect(ctx.getResourceTypePercentage('requirement')).toBe(0)
    expect(ctx.selectedProjectInfo.value).toBeNull()
    expect(ctx.currentProjectId.value).toBe(0)
  })

  it('项目信息与当前项目 ID 随表单变化', async () => {
    await mountHost()
    await ctx.getProjects()

    ctx.formData.project_id = 7
    expect(ctx.selectedProjectInfo.value).toEqual({ id: 7, name: '项目A' })
    expect(ctx.currentProjectId.value).toBe(7)

    ctx.formData.project_id = 99
    expect(ctx.selectedProjectInfo.value).toBeNull()
  })

  it('选择资源写入选中项', async () => {
    await mountHost()
    const row = { id: 3 } as never

    ctx.handleResourceSelect(row)

    expect(ctx.selectedResource.value).toEqual({ id: 3 })
  })
})

describe('testPointExtract — 测试点派生状态', () => {
  it('进度状态三态', async () => {
    await mountHost()

    ctx.progress.value = 40
    expect(ctx.progressStatus.value).toBe('')

    ctx.progress.value = 100
    expect(ctx.progressStatus.value).toBe('success')

    ctx.progress.value = 50
    ctx.errorMessage.value = '失败'
    expect(ctx.progressStatus.value).toBe('exception')
  })

  it('本地分页与数据库分页区别', async () => {
    await mountHost()
    ctx.testPoints.value = Array.from({ length: 25 }, (_, i) => makePoint({ id: i + 1 }))
    ctx.pageSize.value = 10

    ctx.currentPage.value = 2
    expect(ctx.paginatedTestPoints.value).toHaveLength(10)
    expect(ctx.paginatedTestPoints.value[0].id).toBe(11)
    expect(ctx.totalDisplayCount.value).toBe(25)

    ctx.savedFromDb.value = true
    ctx.dbTotal.value = 99
    expect(ctx.paginatedTestPoints.value).toHaveLength(25)
    expect(ctx.totalDisplayCount.value).toBe(99)
  })

  it('模块数与优先级分布', async () => {
    await mountHost()
    ctx.testPoints.value = [
      makePoint({ id: 1, module: 'A', priority: 1 }),
      makePoint({ id: 2, module: 'A', priority: 2 }),
      makePoint({ id: 3, module: '', priority: 3 }),
    ]

    expect(ctx.moduleCount.value).toBe(2)
    expect(ctx.getModuleDistribution()).toEqual({ A: 2, 未分类: 1 })
    expect(ctx.getPriorityCount(1)).toBe(1)
  })

  it('优先级标签与类型映射', async () => {
    await mountHost()

    expect(ctx.getPriorityTagType(1)).toBe('danger')
    expect(ctx.getPriorityTagType('2')).toBe('warning')
    expect(ctx.getPriorityTagType(3)).toBe('info')
    expect(ctx.getPriorityLabel(1)).toBe('高')
    expect(ctx.getPriorityLabel('2')).toBe('中')
    expect(ctx.getPriorityLabel('9')).toBe('低')
  })

  it('加载数据库测试点成功', async () => {
    await mountHost()

    await ctx.loadSavedTestPoints(7, 2)

    expect(mocks.getList).toHaveBeenCalledWith(7, { page: 2, page_size: 10 })
    expect(ctx.testPoints.value).toHaveLength(1)
    expect(ctx.dbTotal.value).toBe(1)
    expect(ctx.savedFromDb.value).toBe(true)
    expect(ctx.currentPage.value).toBe(2)
    expect(ctx.loadingTestPoints.value).toBe(false)
  })

  it('加载数据库测试点失败仅记录日志', async () => {
    mocks.getList.mockRejectedValue(new Error('boom'))
    await mountHost()

    await ctx.loadSavedTestPoints(7)

    expect(console.error).toHaveBeenCalled()
    expect(ctx.loadingTestPoints.value).toBe(false)
  })

  it('分页切换区分数据库模式与本地模式', async () => {
    await mountHost()

    ctx.handlePageChange(3)
    expect(ctx.currentPage.value).toBe(3)
    expect(mocks.getList).not.toHaveBeenCalled()

    ctx.savedFromDb.value = true
    ctx.formData.project_id = 7
    ctx.handlePageChange(4)
    await flushPromises()
    expect(mocks.getList).toHaveBeenCalledWith(7, { page: 4, page_size: 10 })
  })

  it('选择变化与清空选择', async () => {
    await mountHost()
    const rows = [makePoint()]
    const clearSelection = vi.fn()
    ctx.testPointTable.value = { clearSelection } as never

    ctx.handleSelectionChange(rows)
    expect(ctx.selectedRows.value).toEqual(rows)

    ctx.clearSelection()
    expect(ctx.selectedRows.value).toEqual([])
    expect(clearSelection).toHaveBeenCalled()
  })

  it('无表格实例时清空选择不报错', async () => {
    await mountHost()

    expect(() => ctx.clearSelection()).not.toThrow()
  })
})

describe('testPointExtract — 提取流程', () => {
  it('未选文件时 goToExtract 提示', async () => {
    await mountHost()

    ctx.goToExtract()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择需求文件')
    expect(ctx.currentStep.value).toBe(0)
  })

  it('goToExtract 使用传入行并进入第二步', async () => {
    await mountHost()
    const row = { id: 3, project_id: 7, display_name: 'a' } as never

    ctx.goToExtract(row)

    expect(ctx.selectedResource.value).toEqual({ id: 3, project_id: 7, display_name: 'a' })
    expect(ctx.currentStep.value).toBe(2)
  })

  it('startExtract 未选文件时提示', async () => {
    await mountHost()

    ctx.startExtract()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择需求文件')
    expect(mocks.extract).not.toHaveBeenCalled()
  })

  it('startExtract 已选文件时触发提取', async () => {
    await mountHost()
    ctx.selectedResource.value = { id: 3, project_id: 7 } as never

    ctx.startExtract()
    await flushPromises()

    expect(mocks.extract).toHaveBeenCalledWith({ file_id: 3 })
  })

  it('retryExtract 清空错误后重新提取', async () => {
    await mountHost()
    ctx.selectedResource.value = { id: 3, project_id: 7 } as never
    ctx.errorMessage.value = '旧错误'

    ctx.retryExtract()
    await flushPromises()

    expect(mocks.extract).toHaveBeenCalled()
    expect(ctx.errorMessage.value).not.toBe('旧错误')
  })

  it('步骤前进受项目与资源约束', async () => {
    await mountHost()

    ctx.goToNextStep()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
    expect(ctx.currentStep.value).toBe(0)

    ctx.currentStep.value = 1
    ctx.goToNextStep()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择需求资源')
    expect(ctx.currentStep.value).toBe(1)

    ctx.selectedResource.value = { id: 3 } as never
    ctx.goToNextStep()
    expect(ctx.currentStep.value).toBe(2)

    ctx.currentStep.value = 3
    ctx.goToNextStep()
    expect(ctx.currentStep.value).toBe(3)
  })

  it('步骤后退不越过第一步', async () => {
    await mountHost()

    ctx.currentStep.value = 2
    ctx.goToPrevStep()
    expect(ctx.currentStep.value).toBe(1)

    ctx.currentStep.value = 0
    ctx.goToPrevStep()
    expect(ctx.currentStep.value).toBe(0)
  })

  it('提取中重复触发给出提示', async () => {
    await mountHost()
    ctx.selectedResource.value = { id: 3 } as never
    ctx.extracting.value = true

    await ctx.extractTestPoints()

    expect(ElMessage.warning).toHaveBeenCalledWith('正在提取中，请稍候')
  })

  it('提取成功映射字段并保留原始数据', async () => {
    mocks.extract.mockResolvedValue({
      items: [
        { id: 9, module: 'M', point: 'P', priority: 1, ai_prompt: 'prompt', create_time: 't' },
        { module: 'M2', point: 'P2', priority: 'high' },
      ],
    })
    await mountHost()
    ctx.selectedResource.value = { id: 3 } as never

    await ctx.extractTestPoints()

    expect(ctx.testPoints.value).toHaveLength(2)
    expect(ctx.testPoints.value[0]).toMatchObject({ id: 9, module: 'M', priority: 1 })
    expect(ctx.testPoints.value[1].id).toBe(2)
    expect(ctx.testPoints.value[1].priority).toBe(2)
    expect(ctx.testPoints.value[0]._raw).toMatchObject({ module: 'M' })
    expect(ctx.progress.value).toBe(100)
    expect(ctx.progressText.value).toContain('提取完成')
    expect(ctx.extracting.value).toBe(false)
    expect(ElMessage.success).toHaveBeenCalledWith('测试点提取成功，共 2 个')
  })

  it('提取无结果时提示未提取到', async () => {
    mocks.extract.mockResolvedValue({})
    await mountHost()
    ctx.selectedResource.value = { id: 3 } as never

    await ctx.extractTestPoints()

    expect(ElMessage.warning).toHaveBeenCalledWith('未提取到测试点')
    expect(ctx.progress.value).toBe(100)
  })

  it('提取失败展示接口 detail 并截断超长内容', async () => {
    mocks.extract.mockRejectedValue({ response: { data: { detail: 'x'.repeat(300) } } })
    await mountHost()
    ctx.selectedResource.value = { id: 3 } as never

    await ctx.extractTestPoints()

    expect(ctx.errorMessage.value).toHaveLength(203)
    expect(ctx.errorMessage.value.endsWith('...')).toBe(true)
    expect(ElMessage.error).toHaveBeenCalledWith('提取失败，请查看错误信息')
    expect(ctx.progress.value).toBe(0)
    expect(ctx.extracting.value).toBe(false)
  })

  it('堆栈类 detail 回退到 message 字段', async () => {
    mocks.extract.mockRejectedValue({
      response: { data: { detail: 'Traceback: traceback boom', message: '服务繁忙' } },
    })
    await mountHost()
    ctx.selectedResource.value = { id: 3 } as never

    await ctx.extractTestPoints()

    expect(ctx.errorMessage.value).toBe('服务繁忙')
  })

  it('无可用错误信息时使用默认文案', async () => {
    mocks.extract.mockRejectedValue(new Error('boom'))
    await mountHost()
    ctx.selectedResource.value = { id: 3 } as never

    await ctx.extractTestPoints()

    expect(ctx.errorMessage.value).toBe('测试点提取失败，请检查网络连接或稍后重试')
  })

  it('提取过程按阶段推进进度', async () => {
    const extracting = deferred<unknown>()
    mocks.extract.mockReturnValue(extracting.promise)
    await mountHost()
    vi.useFakeTimers()
    ctx.selectedResource.value = { id: 3 } as never

    const pending = ctx.extractTestPoints()
    vi.advanceTimersByTime(1200)
    expect(ctx.progress.value).toBeGreaterThan(0)
    expect(ctx.progressText.value).toBe('正在读取文件内容...')

    extracting.resolve({ items: [] })
    await pending
    expect(ctx.progress.value).toBe(100)
  })

  it('取消提取确认后重置进度', async () => {
    await mountHost()
    ctx.extracting.value = true
    ctx.progress.value = 60

    ctx.handleCancel()
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(ctx.extracting.value).toBe(false)
    expect(ctx.progress.value).toBe(0)
    expect(ctx.progressText.value).toBe('已取消')
    expect(ElMessage.info).toHaveBeenCalledWith('提取已取消')
  })

  it('取消提取被拒绝时不重置', async () => {
    // 模拟用户取消：then 回调不会执行
    vi.spyOn(ElMessageBox, 'confirm').mockImplementation(
      () => ({ then: () => Promise.resolve(), catch: () => Promise.resolve() }) as never
    )
    await mountHost()
    ctx.extracting.value = true
    ctx.progress.value = 60

    ctx.handleCancel()
    await flushPromises()

    expect(ctx.extracting.value).toBe(true)
    expect(ctx.progress.value).toBe(60)
  })
})

describe('testPointExtract — 测试点操作', () => {
  it('批量删除未选择时提示', async () => {
    await mountHost()

    await ctx.batchDeleteTestPoints()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择要删除的测试点')
  })

  it('批量删除未选项目时提示', async () => {
    await mountHost()
    ctx.selectedRows.value = [makePoint()]

    await ctx.batchDeleteTestPoints()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
  })

  it('批量删除成功后过滤本地数据并清空选择', async () => {
    await mountHost()
    ctx.formData.project_id = 7
    ctx.testPoints.value = [makePoint({ id: 1 }), makePoint({ id: 2 }), makePoint({ id: 3 })]
    ctx.selectedRows.value = [makePoint({ id: 1 }), makePoint({ id: 2 })]

    await ctx.batchDeleteTestPoints()

    expect(mocks.batchDelete).toHaveBeenCalledWith(7, [1, 2])
    expect(ctx.testPoints.value).toHaveLength(1)
    expect(ctx.selectedRows.value).toEqual([])
    expect(ElMessage.success).toHaveBeenCalledWith('成功删除 2 个测试点')
    expect(ctx.batchDeleting.value).toBe(false)
  })

  it('数据库模式批量删除后重新拉取当前页', async () => {
    await mountHost()
    ctx.formData.project_id = 7
    ctx.savedFromDb.value = true
    ctx.currentPage.value = 2
    ctx.selectedRows.value = [makePoint({ id: 1 })]

    await ctx.batchDeleteTestPoints()

    expect(mocks.getList).toHaveBeenCalledWith(7, { page: 2, page_size: 10 })
  })

  it('批量删除接口返回非 200 时提示错误', async () => {
    mocks.batchDelete.mockResolvedValue({ code: 500, message: '服务异常' })
    await mountHost()
    ctx.formData.project_id = 7
    ctx.selectedRows.value = [makePoint()]

    await ctx.batchDeleteTestPoints()

    expect(ElMessage.error).toHaveBeenCalledWith('服务异常')
  })

  it('批量删除取消时静默', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel' as never)
    await mountHost()
    ctx.formData.project_id = 7
    ctx.selectedRows.value = [makePoint()]

    await ctx.batchDeleteTestPoints()

    expect(mocks.batchDelete).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('空 message 时使用接口返回的删除数量', async () => {
    mocks.batchDelete.mockResolvedValue({ code: 200, data: { deleted_count: 5 } })
    await mountHost()
    ctx.formData.project_id = 7
    ctx.selectedRows.value = [makePoint()]

    await ctx.batchDeleteTestPoints()

    expect(ElMessage.success).toHaveBeenCalledWith('成功删除 5 个测试点')
  })

  it('编辑测试点回填表单', async () => {
    await mountHost()
    ctx.testPoints.value = [makePoint({ id: 1, function: 'F', priority: 2 })]

    ctx.editTestPoint(makePoint({ id: 1, function: 'F', priority: 2 }))

    expect(ctx.editingIndex.value).toBe(0)
    expect(ctx.editForm).toMatchObject({ id: 1, module: '模块A', function: 'F', priority: 2 })
    expect(ctx.dialogVisible.value).toBe(true)
  })

  it('保存测试点缺少必填项时提示', async () => {
    await mountHost()
    ctx.editForm.id = 1
    ctx.editForm.module = ''
    ctx.editForm.point = ''

    await ctx.saveTestPoint()

    expect(ElMessage.warning).toHaveBeenCalledWith('请填写完整的测试点信息')
  })

  it('数据库模式保存调用更新接口', async () => {
    await mountHost()
    ctx.formData.project_id = 7
    ctx.savedFromDb.value = true
    ctx.testPoints.value = [makePoint({ id: 1, ai_prompt: 'p' })]
    Object.assign(ctx.editForm, { id: 1, module: 'M', function: 'F', point: 'P', priority: 1 })
    ctx.editingIndex.value = 0

    await ctx.saveTestPoint()

    expect(mocks.update).toHaveBeenCalledWith(1, {
      project_id: 7,
      module: 'M',
      function: 'F',
      point: 'P',
      priority: 1,
      ai_prompt: 'p',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('测试点更新成功')
    expect(ctx.dialogVisible.value).toBe(false)
    expect(mocks.getList).toHaveBeenCalled()
    expect(ctx.updating.value).toBe(false)
  })

  it('本地模式保存只更新内存', async () => {
    await mountHost()
    ctx.testPoints.value = [makePoint({ id: 1 })]
    Object.assign(ctx.editForm, { id: 1, module: 'M2', point: 'P2', priority: 3 })
    ctx.editingIndex.value = 0

    await ctx.saveTestPoint()

    expect(mocks.update).not.toHaveBeenCalled()
    expect(ctx.testPoints.value[0].module).toBe('M2')
    expect(ElMessage.success).toHaveBeenCalledWith('测试点更新成功（本地）')
  })

  it('保存测试点失败提示错误', async () => {
    mocks.update.mockResolvedValue({ code: 500, message: '更新失败' })
    await mountHost()
    ctx.formData.project_id = 7
    ctx.savedFromDb.value = true
    ctx.testPoints.value = [makePoint({ id: 1 })]
    Object.assign(ctx.editForm, { id: 1, module: 'M', point: 'P', priority: 1 })
    ctx.editingIndex.value = 0

    await ctx.saveTestPoint()

    expect(ElMessage.error).toHaveBeenCalledWith('更新失败')
    expect(ctx.updating.value).toBe(false)
  })

  it('删除测试点未选项目时提示', async () => {
    await mountHost()

    await ctx.deleteTestPoint(makePoint())

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
  })

  it('数据库模式删除后按最大页修正页码', async () => {
    mocks.delete.mockResolvedValue({ code: 200 })
    await mountHost()
    ctx.formData.project_id = 7
    ctx.savedFromDb.value = true
    ctx.dbTotal.value = 11
    ctx.pageSize.value = 10
    ctx.currentPage.value = 2

    await ctx.deleteTestPoint(makePoint({ id: 1 }))

    expect(mocks.delete).toHaveBeenCalledWith(1, 7)
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(mocks.getList).toHaveBeenCalledWith(7, { page: 1, page_size: 10 })
  })

  it('数据库模式删除返回非 200 时提示', async () => {
    mocks.delete.mockResolvedValue({ code: 500, message: '删除失败' })
    await mountHost()
    ctx.formData.project_id = 7
    ctx.savedFromDb.value = true

    await ctx.deleteTestPoint(makePoint({ id: 1 }))

    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })

  it('本地模式删除直接移除项', async () => {
    await mountHost()
    ctx.formData.project_id = 7
    ctx.testPoints.value = [makePoint({ id: 1 }), makePoint({ id: 2 })]

    await ctx.deleteTestPoint(makePoint({ id: 1 }))

    expect(mocks.delete).not.toHaveBeenCalled()
    expect(ctx.testPoints.value).toHaveLength(1)
    expect(ctx.testPoints.value[0].id).toBe(2)
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功（本地）')
  })

  it('删除异常提示错误', async () => {
    mocks.delete.mockRejectedValue({ response: { data: { detail: '关联用例存在' } } })
    await mountHost()
    ctx.formData.project_id = 7
    ctx.savedFromDb.value = true

    await ctx.deleteTestPoint(makePoint({ id: 1 }))

    expect(ElMessage.error).toHaveBeenCalledWith('关联用例存在')
    expect(ctx.deleting.value).toBe(false)
  })

  it('保存到数据库无测试点时提示', async () => {
    await mountHost()

    await ctx.saveToDatabase()

    expect(ElMessage.warning).toHaveBeenCalledWith('没有可保存的测试点')
  })

  it('保存到数据库无项目时提示', async () => {
    await mountHost()
    ctx.testPoints.value = [makePoint()]

    await ctx.saveToDatabase()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
  })

  it('保存到数据库过滤无效数据', async () => {
    await mountHost()
    ctx.formData.project_id = 7
    ctx.testPoints.value = [{ id: 1, module: '', point: '', priority: 1 }]

    await ctx.saveToDatabase()

    expect(ElMessage.warning).toHaveBeenCalledWith('没有有效的测试点数据')
    expect(mocks.batchSave).not.toHaveBeenCalled()
    expect(ctx.saving.value).toBe(false)
  })

  it('保存到数据库成功并刷新列表', async () => {
    await mountHost()
    ctx.formData.project_id = 7
    ctx.testPoints.value = [makePoint({ _raw: { module: 'M', point: 'P', priority: 1 } })]

    await ctx.saveToDatabase()

    expect(mocks.batchSave).toHaveBeenCalledWith(7, [{ module: 'M', point: 'P', priority: 1 }])
    expect(ElMessage.success).toHaveBeenCalledWith('保存成功')
    expect(ctx.savedFromDb.value).toBe(true)
    expect(mocks.getList).toHaveBeenCalled()
    expect(ctx.saving.value).toBe(false)
  })

  it('保存到数据库返回非 200 时提示', async () => {
    mocks.batchSave.mockResolvedValue({ code: 500, message: '写入失败' })
    await mountHost()
    ctx.formData.project_id = 7
    ctx.testPoints.value = [makePoint()]

    await ctx.saveToDatabase()

    expect(ElMessage.error).toHaveBeenCalledWith('写入失败')
  })

  it('保存到数据库异常时兜底提示', async () => {
    mocks.batchSave.mockRejectedValue(new Error('boom'))
    await mountHost()
    ctx.formData.project_id = 7
    ctx.testPoints.value = [makePoint()]

    await ctx.saveToDatabase()

    expect(ElMessage.error).toHaveBeenCalledWith('boom')
    expect(ctx.saving.value).toBe(false)
  })

  it('生成用例携带项目与测试点 ID', async () => {
    await mountHost()
    ctx.formData.project_id = 7
    ctx.testPoints.value = [makePoint({ id: 1 }), makePoint({ id: 2 })]
    ctx.selectedResource.value = { id: 3, display_name: '需求.pdf' } as never

    ctx.generateTestCases()

    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/case/smart-generate',
      query: {
        project_id: '7',
        test_point_ids: '[1,2]',
        file_id: '3',
        filename: '需求.pdf',
      },
    })
  })

  it('生成用例无测试点或无项目时提示', async () => {
    await mountHost()

    ctx.generateTestCases()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先提取或加载测试点')

    ctx.testPoints.value = [makePoint()]
    ctx.generateTestCases()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('跳转测试点管理按项目 ID 附加参数', async () => {
    await mountHost()
    ctx.formData.project_id = 7

    ctx.goToManagement()

    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/case/test-point-management',
      query: { projectId: '7' },
    })
  })

  it('无项目时跳转不带参数', async () => {
    await mountHost()

    ctx.goToManagement()

    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/case/test-point-management',
      query: {},
    })
  })
})

describe('testPointExtract — 初始化与上下文', () => {
  it('切换项目时加载资源与已保存测试点', async () => {
    await mountHost()
    ctx.testPoints.value = [makePoint()]
    ctx.savedFromDb.value = true
    ctx.dbTotal.value = 5

    await ctx.handleProjectChange(7)

    expect(mocks.getFileListByProject).toHaveBeenCalledWith(7)
    expect(mocks.getList).toHaveBeenCalledWith(7, { page: 1, page_size: 10 })
    expect(ctx.selectedResource.value).toBeNull()
    expect(ctx.currentPage.value).toBe(1)
    expect(ctx.errorMessage.value).toBe('')
  })

  it('清空项目时重置状态且不发请求', async () => {
    await mountHost()
    ctx.testPoints.value = [makePoint()]
    ctx.savedFromDb.value = true

    await ctx.handleProjectChange(0)

    expect(mocks.getFileListByProject).not.toHaveBeenCalled()
    expect(ctx.files.value).toEqual([])
    expect(ctx.testPoints.value).toEqual([])
    expect(ctx.savedFromDb.value).toBe(false)
    expect(ctx.dbTotal.value).toBe(0)
    expect(ctx.currentPage.value).toBe(1)
  })

  it('init 依据路由参数加载项目并选中资源', async () => {
    mocks.route.query = { project_id: '7', file_id: '3' }
    await mountHost()

    await ctx.init()

    expect(mocks.getProjects).toHaveBeenCalled()
    expect(ctx.formData.project_id).toBe(7)
    expect(mocks.getFileListByProject).toHaveBeenCalledWith(7)
    expect(mocks.getList).toHaveBeenCalled()
    expect(ctx.selectedResource.value?.id).toBe(3)
  })

  it('init 无路由参数时只加载项目', async () => {
    await mountHost()

    await ctx.init()

    expect(mocks.getProjects).toHaveBeenCalled()
    expect(ctx.formData.project_id).toBe('')
    expect(mocks.getFileListByProject).not.toHaveBeenCalled()
  })

  it('file_id 未命中资源时不选中', async () => {
    mocks.route.query = { project_id: '7', file_id: '99' }
    await mountHost()

    await ctx.init()

    expect(ctx.selectedResource.value).toBeNull()
  })

  it('cleanup 清理进度定时器', async () => {
    await mountHost()
    vi.useFakeTimers()
    mocks.extract.mockImplementation(() => new Promise(() => {}))
    ctx.selectedResource.value = { id: 3 } as never

    ctx.extractTestPoints()
    expect(vi.getTimerCount()).toBeGreaterThan(0)

    ctx.cleanup()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('未提供上下文时 useTestPointExtract 抛错', () => {
    expect(() => useTestPointExtract()).toThrow(/must be called within a component tree/)
  })
})
