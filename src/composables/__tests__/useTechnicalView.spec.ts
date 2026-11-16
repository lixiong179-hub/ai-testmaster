import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const mocks = vi.hoisted(() => ({
  getTechnicalView: vi.fn(),
}))

vi.mock('@/api/testCaseView', () => {
  const api = { getTechnicalView: mocks.getTechnicalView }
  return { testCaseViewApi: api, default: api }
})

import { silenceConsole, silenceElMessage } from '@/test-utils'
import { useTechnicalView, VIEW_TYPES } from '../useTechnicalView'

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage('error')
  silenceConsole('error')
  mocks.getTechnicalView.mockResolvedValue({ steps: [{ step_number: 1 }] })
})

describe('useTechnicalView — 数据加载', () => {
  it('初始状态为业务视图', () => {
    const { currentView, viewLoading, technicalViewData } = useTechnicalView(ref(42))

    expect(currentView.value).toBe(VIEW_TYPES.BUSINESS)
    expect(viewLoading.value).toBe(false)
    expect(technicalViewData.value).toBeNull()
  })

  it('缺少用例 ID 时不请求', async () => {
    const { fetchTechnicalView, viewLoading } = useTechnicalView(ref(0))

    await fetchTechnicalView()

    expect(mocks.getTechnicalView).not.toHaveBeenCalled()
    expect(viewLoading.value).toBe(false)
  })

  it('加载成功写入技术视图数据', async () => {
    const { fetchTechnicalView, technicalViewData, viewLoading } = useTechnicalView(ref(42))

    await fetchTechnicalView()

    expect(mocks.getTechnicalView).toHaveBeenCalledWith(42)
    expect(technicalViewData.value).toEqual({ steps: [{ step_number: 1 }] })
    expect(viewLoading.value).toBe(false)
  })

  it('加载失败优先展示接口 detail', async () => {
    mocks.getTechnicalView.mockRejectedValue({ response: { data: { detail: '用例不存在' } } })
    const { fetchTechnicalView } = useTechnicalView(ref(42))

    await fetchTechnicalView()

    expect(ElMessage.error).toHaveBeenCalledWith('用例不存在')
  })

  it('加载失败回退 message 与默认文案', async () => {
    mocks.getTechnicalView.mockRejectedValueOnce(new Error('网络异常'))
    const { fetchTechnicalView } = useTechnicalView(ref(42))
    await fetchTechnicalView()
    expect(ElMessage.error).toHaveBeenCalledWith('网络异常')

    mocks.getTechnicalView.mockRejectedValueOnce({})
    await fetchTechnicalView()
    expect(ElMessage.error).toHaveBeenLastCalledWith('获取技术视图失败')
  })
})

describe('useTechnicalView — 视图切换', () => {
  it('切换到相同视图不做处理', async () => {
    const { handleViewChange } = useTechnicalView(ref(42))

    await handleViewChange(VIEW_TYPES.BUSINESS)

    expect(mocks.getTechnicalView).not.toHaveBeenCalled()
  })

  it('切换到技术视图自动拉取数据', async () => {
    const { handleViewChange, currentView, technicalViewData } = useTechnicalView(ref(42))

    await handleViewChange(VIEW_TYPES.TECHNICAL)

    expect(currentView.value).toBe(VIEW_TYPES.TECHNICAL)
    expect(mocks.getTechnicalView).toHaveBeenCalledWith(42)
    expect(technicalViewData.value).not.toBeNull()
  })

  it('从技术视图切回业务视图不重复请求', async () => {
    const { handleViewChange, currentView } = useTechnicalView(ref(42))
    await handleViewChange(VIEW_TYPES.TECHNICAL)
    mocks.getTechnicalView.mockClear()

    await handleViewChange(VIEW_TYPES.BUSINESS)

    expect(currentView.value).toBe(VIEW_TYPES.BUSINESS)
    expect(mocks.getTechnicalView).not.toHaveBeenCalled()
  })
})

describe('useTechnicalView — 展示辅助', () => {
  it('定位状态类型与文案映射', () => {
    const { getLocatorStatusType, getLocatorStatusLabel } = useTechnicalView(ref(42))

    expect(getLocatorStatusType('recorded')).toBe('success')
    expect(getLocatorStatusType('pending')).toBe('warning')
    expect(getLocatorStatusType('failed')).toBe('danger')
    expect(getLocatorStatusType('unknown')).toBe('info')

    expect(getLocatorStatusLabel('recorded')).toBe('已定位')
    expect(getLocatorStatusLabel('pending')).toBe('待定位')
    expect(getLocatorStatusLabel('failed')).toBe('定位失败')
    expect(getLocatorStatusLabel('unknown')).toBe('unknown')
  })

  it('覆盖率格式化兼容数字与字符串', () => {
    const { formatLocatorCoverage } = useTechnicalView(ref(42))

    expect(formatLocatorCoverage(80)).toBe('80.0%')
    expect(formatLocatorCoverage('90%')).toBe('90%')
    expect(formatLocatorCoverage('90')).toBe('90%')
  })
})
