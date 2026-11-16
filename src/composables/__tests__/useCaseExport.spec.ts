import { describe, it, expect, beforeEach, vi } from 'vitest'
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

vi.mock('@/api/testCaseView', () => ({
  testCaseViewApi: {
    exportToFunctionalExcel: vi.fn(),
  },
}))

vi.mock('@/utils/download', () => ({
  downloadFromResponse: vi.fn(),
  parseBlobError: vi.fn(),
}))

import { testCaseViewApi } from '@/api/testCaseView'
import { downloadFromResponse, parseBlobError } from '@/utils/download'
import { useCaseExport } from '../useCaseExport'
import type { TestCase } from '@/api/case'
import { silenceConsole, silenceElMessage } from '@/test-utils'

const exportMock = vi.mocked(testCaseViewApi.exportToFunctionalExcel)
const downloadMock = vi.mocked(downloadFromResponse)
const parseErrorMock = vi.mocked(parseBlobError)

function setup(allIds = [1, 2, 3], selected: number[] = []) {
  const allSource = ref<TestCase[]>(allIds.map((id) => ({ id, title: `用例${id}` }) as TestCase))
  const selectedCases = ref<number[]>(selected)

  const api = useCaseExport({
    filteredTestCases: computed(() => allSource.value),
    selectedCases,
  })
  return { api, allSource, selectedCases }
}

describe('useCaseExport — 导出结果断言', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    exportMock.mockResolvedValue({ headers: {} } as never)
    parseErrorMock.mockResolvedValue('导出失败，请稍后重试')
    silenceElMessage('warning')
    silenceElMessage('error')
    silenceElMessage('success')
    silenceConsole('error')
  })

  it('空ID列表直接提示且不请求', async () => {
    const { api } = setup()

    await api.exportFunctionalExcel([])

    expect(ElMessage.warning).toHaveBeenCalledWith('暂无可导出的用例')
    expect(exportMock).not.toHaveBeenCalled()
  })

  it('导出成功：下载文件名按日期兜底并提示条数', async () => {
    const { api } = setup()

    await api.exportFunctionalExcel([1, 2])

    const fallback = `功能测试用例_${new Date().toISOString().slice(0, 10)}.xlsx`
    expect(exportMock).toHaveBeenCalledWith([1, 2])
    expect(downloadMock).toHaveBeenCalledWith({ headers: {} }, fallback)
    expect(ElMessage.success).toHaveBeenCalledWith('已导出 2 条用例')
    expect(api.exporting.value).toBe(false)
  })

  it('存在权限跳过数时改用 warning 并给出差额', async () => {
    exportMock.mockResolvedValue({ headers: { 'x-export-skipped-count': '2' } } as never)
    const { api } = setup()

    await api.exportFunctionalExcel([1, 2, 3])

    expect(ElMessage.warning).toHaveBeenCalledWith('已导出 1 条用例，2 条因权限被忽略')
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('跳过数为 0 时按普通成功处理', async () => {
    exportMock.mockResolvedValue({ headers: { 'x-export-skipped-count': '0' } } as never)
    const { api } = setup()

    await api.exportFunctionalExcel([1])

    expect(ElMessage.success).toHaveBeenCalledWith('已导出 1 条用例')
  })

  it('导出异常时使用 parseBlobError 的文案', async () => {
    exportMock.mockRejectedValue(new Error('boom'))
    parseErrorMock.mockResolvedValue('无导出权限')
    const { api } = setup()

    await api.exportFunctionalExcel([1])

    expect(parseErrorMock).toHaveBeenCalledWith(expect.any(Error), '导出失败，请稍后重试')
    expect(ElMessage.error).toHaveBeenCalledWith('无导出权限')
    expect(api.exporting.value).toBe(false)
  })
})

describe('useCaseExport — 全量/选中导出', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    exportMock.mockResolvedValue({ headers: {} } as never)
    silenceElMessage('warning')
    silenceElMessage('success')
  })

  it('导出全部按当前筛选结果取ID', async () => {
    const { api } = setup([5, 6])

    await api.handleExportAll()

    expect(exportMock).toHaveBeenCalledWith([5, 6])
  })

  it('未选中时提示先选择', async () => {
    const { api } = setup([1], [])

    api.handleExportSelected()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择要导出的用例')
    expect(exportMock).not.toHaveBeenCalled()
  })

  it('导出选中时传副本，后续选择变更不影响已发起请求', async () => {
    const { api, selectedCases } = setup([1, 2], [1, 2])

    await api.handleExportSelected()
    selectedCases.value.push(3)

    expect(exportMock).toHaveBeenCalledWith([1, 2])
  })
})
