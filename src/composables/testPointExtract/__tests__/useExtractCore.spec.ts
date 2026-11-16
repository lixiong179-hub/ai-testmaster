import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { deferred, mockConfirm, silenceConsole, silenceElMessage } from '@/test-utils'
import type { ExtractSharedState, ResourceRow } from '../types'

const mocks = vi.hoisted(() => ({
  extract: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ query: {} }),
}))

vi.mock('@/api/testPoint', () => ({
  testPointApi: { extract: mocks.extract },
}))

import { createSharedState } from '../createSharedState'
import { useExtractCore } from '../useExtractCore'

let state: ExtractSharedState
let core: ReturnType<typeof useExtractCore>

function makeRow(overrides: Partial<ResourceRow> = {}): ResourceRow {
  return {
    source: 'file',
    id: 5,
    project_id: 9,
    display_name: '需求.docx',
    resource_type: 'requirement',
    type_label: '需求文档',
    size_text: '2.00 KB',
    time_text: '2026-06-27 10:00:00',
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  silenceConsole()
  mockConfirm()
  state = createSharedState()
  core = useExtractCore(state)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useExtractCore — 步骤流转', () => {
  it('未选中资源时提示先选需求文件', () => {
    core.goToExtract()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择需求文件')
    expect(state.currentStep.value).toBe(0)
  })

  it('指定资源行时写入选中并跳到第 3 步', () => {
    const row = makeRow()

    core.goToExtract(row)

    expect(state.selectedResource.value).toEqual(row)
    expect(state.currentStep.value).toBe(2)
  })

  it('未指定资源行时使用已选资源', () => {
    state.selectedResource.value = makeRow({ id: 8 })

    core.goToExtract()

    expect(state.currentStep.value).toBe(2)
  })

  it('第 1 步未选项目时拦截', () => {
    core.goToNextStep()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
    expect(state.currentStep.value).toBe(0)
  })

  it('第 2 步未选资源时拦截', () => {
    state.formData.project_id = 9
    state.currentStep.value = 1

    core.goToNextStep()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择需求资源')
    expect(state.currentStep.value).toBe(1)
  })

  it('条件满足时前进一步，且不超过第 4 步', () => {
    state.formData.project_id = 9
    core.goToNextStep()
    expect(state.currentStep.value).toBe(1)

    state.selectedResource.value = makeRow()
    core.goToNextStep()
    expect(state.currentStep.value).toBe(2)

    core.goToNextStep()
    expect(state.currentStep.value).toBe(3)

    core.goToNextStep()
    expect(state.currentStep.value).toBe(3)
  })

  it('上一步不会低于第 1 步', () => {
    core.goToPrevStep()
    expect(state.currentStep.value).toBe(0)

    state.currentStep.value = 2
    core.goToPrevStep()
    expect(state.currentStep.value).toBe(1)
  })
})

describe('useExtractCore — 提取流程', () => {
  it('未选资源时 startExtract 提示且不请求接口', () => {
    core.startExtract()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择需求文件')
    expect(mocks.extract).not.toHaveBeenCalled()
  })

  it('提取成功后映射测试点并重置进度状态', async () => {
    state.selectedResource.value = makeRow({ id: 5 })
    state.testPoints.value = [{ id: 99, module: '旧', point: '旧', priority: 1 }]
    state.savedFromDb.value = true
    state.dbTotal.value = 30
    state.currentPage.value = 3
    mocks.extract.mockResolvedValue({
      items: [
        { id: 1, module: '登录', point: '登录成功', priority: 1, ai_prompt: 'p' },
        { module: '登录', point: '登录失败', priority: '2' },
      ],
    })

    await core.extractTestPoints()

    expect(mocks.extract).toHaveBeenCalledWith({ file_id: 5 })
    expect(state.testPoints.value).toEqual([
      {
        id: 1,
        module: '登录',
        point: '登录成功',
        priority: 1,
        ai_prompt: 'p',
        create_time: undefined,
        _raw: { id: 1, module: '登录', point: '登录成功', priority: 1, ai_prompt: 'p' },
      },
      {
        id: 2,
        module: '登录',
        point: '登录失败',
        priority: 2,
        ai_prompt: undefined,
        create_time: undefined,
        _raw: { module: '登录', point: '登录失败', priority: '2' },
      },
    ])
    expect(state.savedFromDb.value).toBe(false)
    expect(state.dbTotal.value).toBe(0)
    expect(state.currentPage.value).toBe(1)
    expect(state.progress.value).toBe(100)
    expect(state.progressText.value).toBe('提取完成！共 2 个测试点')
    expect(state.extracting.value).toBe(false)
    expect(ElMessage.success).toHaveBeenCalledWith('测试点提取成功，共 2 个')
  })

  it('接口无 items 时提示未提取到测试点', async () => {
    state.selectedResource.value = makeRow()
    mocks.extract.mockResolvedValue({})

    await core.extractTestPoints()

    expect(ElMessage.warning).toHaveBeenCalledWith('未提取到测试点')
    expect(state.testPoints.value).toEqual([])
    expect(state.progress.value).toBe(100)
  })

  it('提取中重复触发时提示稍候', async () => {
    state.selectedResource.value = makeRow()
    state.extracting.value = true

    await core.extractTestPoints()

    expect(ElMessage.warning).toHaveBeenCalledWith('正在提取中，请稍候')
    expect(mocks.extract).not.toHaveBeenCalled()
  })

  it('提取过程中进度按阶段推进', async () => {
    vi.useFakeTimers()
    state.selectedResource.value = makeRow()
    const pending = deferred<{ items: unknown[] }>()
    mocks.extract.mockReturnValue(pending.promise)

    const task = core.extractTestPoints()
    await vi.advanceTimersByTimeAsync(300)

    expect(state.progress.value).toBeGreaterThan(0)
    expect(state.progressText.value).not.toBe('')

    pending.resolve({ items: [] })
    await task
  })

  it('retryExtract 先清空错误信息再重新提取', async () => {
    state.selectedResource.value = makeRow()
    state.errorMessage.value = '上次失败'
    mocks.extract.mockResolvedValue({ items: [] })

    core.retryExtract()
    await flushPromises()

    expect(mocks.extract).toHaveBeenCalledTimes(1)
  })

  it('失败时按接口 detail 记录错误（超长截断到 200 字）', async () => {
    state.selectedResource.value = makeRow()
    const detail = 'x'.repeat(260)
    mocks.extract.mockRejectedValue({ response: { data: { detail } } })

    await core.extractTestPoints()

    expect(state.errorMessage.value).toBe(detail.slice(0, 200) + '...')
    expect(state.progress.value).toBe(0)
    expect(ElMessage.error).toHaveBeenCalledWith('提取失败，请查看错误信息')
  })

  it('detail 含堆栈信息时改用 message', async () => {
    state.selectedResource.value = makeRow()
    mocks.extract.mockRejectedValue({
      response: { data: { detail: 'traceback: at foo', message: '服务异常' } },
    })

    await core.extractTestPoints()

    expect(state.errorMessage.value).toBe('服务异常')
  })

  it('无可用错误信息时使用兜底文案', async () => {
    state.selectedResource.value = makeRow()
    mocks.extract.mockRejectedValue(new Error('network'))

    await core.extractTestPoints()

    expect(state.errorMessage.value).toBe('测试点提取失败，请检查网络连接或稍后重试')
    expect(state.extracting.value).toBe(false)
  })

  it('取消确认后清理定时器并复位进度', async () => {
    vi.useFakeTimers()
    state.extracting.value = true
    state.progress.value = 40
    state.progressInterval.value = setInterval(() => {}, 300)

    core.handleCancel()
    // 假定时器下不能使用 flushPromises（内部依赖 setTimeout）
    await vi.advanceTimersByTimeAsync(0)

    expect(state.progressInterval.value).toBeNull()
    expect(state.extracting.value).toBe(false)
    expect(state.progress.value).toBe(0)
    expect(state.progressText.value).toBe('已取消')
    expect(ElMessage.info).toHaveBeenCalledWith('提取已取消')
  })
})
