import { describe, it, expect, vi, beforeEach } from 'vitest'

const mocks = vi.hoisted(() => ({
  onAuthEvent: vi.fn(),
  resetProject: vi.fn(),
  resetCase: vi.fn(),
  resetTask: vi.fn(),
  resetReport: vi.fn(),
  resetQuickTest: vi.fn(),
  resetSmartGeneration: vi.fn(),
  resetFlowSort: vi.fn(),
}))

vi.mock('../authEventBus', () => ({
  onAuthEvent: mocks.onAuthEvent,
  emitAuthEvent: vi.fn(),
}))

vi.mock('@/store/project', () => ({
  useProjectStore: () => ({ $reset: mocks.resetProject }),
}))
vi.mock('@/store/case', () => ({ useCaseStore: () => ({ $reset: mocks.resetCase }) }))
vi.mock('@/store/task', () => ({ useTaskStore: () => ({ $reset: mocks.resetTask }) }))
vi.mock('@/store/report', () => ({ useReportStore: () => ({ $reset: mocks.resetReport }) }))
vi.mock('@/store/quickTest', () => ({
  useQuickTestStore: () => ({ reset: mocks.resetQuickTest }),
}))
vi.mock('@/store/smartGeneration', () => ({
  useSmartGenerationStore: () => ({ reset: mocks.resetSmartGeneration }),
}))
vi.mock('@/store/flowSort', () => ({ useFlowSortStore: () => ({ reset: mocks.resetFlowSort }) }))

import { registerAuthCleanup } from '../registerAuthCleanup'

/** 取出注册到事件总线上的清理回调 */
function getCleanupHandler(): () => void {
  const calls = mocks.onAuthEvent.mock.calls
  const call = calls[calls.length - 1]
  return call?.[1] as () => void
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('registerAuthCleanup — 注册', () => {
  it('监听 auth:unauthorized 事件', () => {
    registerAuthCleanup()

    expect(mocks.onAuthEvent).toHaveBeenCalledWith('auth:unauthorized', expect.any(Function))
  })
})

describe('registerAuthCleanup — 清理回调', () => {
  it('触发时重置全部业务 Store', () => {
    registerAuthCleanup()

    getCleanupHandler()()

    expect(mocks.resetProject).toHaveBeenCalled()
    expect(mocks.resetCase).toHaveBeenCalled()
    expect(mocks.resetTask).toHaveBeenCalled()
    expect(mocks.resetReport).toHaveBeenCalled()
    expect(mocks.resetQuickTest).toHaveBeenCalled()
    expect(mocks.resetSmartGeneration).toHaveBeenCalled()
    expect(mocks.resetFlowSort).toHaveBeenCalled()
  })

  it('单个 Store 重置失败不影响其余', () => {
    mocks.resetProject.mockImplementation(() => {
      throw new Error('Pinia 未初始化')
    })
    registerAuthCleanup()

    expect(() => getCleanupHandler()()).not.toThrow()
    expect(mocks.resetCase).toHaveBeenCalled()
    expect(mocks.resetFlowSort).toHaveBeenCalled()
  })

  it('Pinia 未初始化时全部失败也不抛错', () => {
    for (const reset of [
      mocks.resetProject,
      mocks.resetCase,
      mocks.resetTask,
      mocks.resetReport,
      mocks.resetQuickTest,
      mocks.resetSmartGeneration,
      mocks.resetFlowSort,
    ]) {
      reset.mockImplementation(() => {
        throw new Error('no active pinia')
      })
    }
    registerAuthCleanup()

    expect(() => getCleanupHandler()()).not.toThrow()
  })
})
