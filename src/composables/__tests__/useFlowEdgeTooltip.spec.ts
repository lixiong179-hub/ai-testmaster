import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useFlowEdgeTooltip } from '../useFlowEdgeTooltip'
import type { EdgeMouseEvent } from '@vue-flow/core'

function mouseEvent(x: number, y: number, edgeId = 'e1'): EdgeMouseEvent {
  return {
    event: { clientX: x, clientY: y } as MouseEvent,
    edge: { id: edgeId, source: 'a', target: 'b', label: '主干' },
  } as unknown as EdgeMouseEvent
}

describe('useFlowEdgeTooltip — 悬停显示', () => {
  it('mouseenter 记录边数据并把 tooltip 偏移 12px 显示', () => {
    const api = useFlowEdgeTooltip({})

    api.onEdgeMouseEnter(mouseEvent(100, 200, 'e9'))

    expect(api.edgeTooltipVisible.value).toBe(true)
    expect(api.edgeTooltipData.value).toMatchObject({ id: 'e9', label: '主干' })
    expect(api.edgeTooltipPosition.value).toEqual({ x: 112, y: 212 })
  })

  it('已显示时 mousemove 不再更新位置（避免跟随鼠标导致无法点击）', () => {
    const api = useFlowEdgeTooltip({})
    api.onEdgeMouseEnter(mouseEvent(100, 200))

    api.onEdgeMouseMove(mouseEvent(500, 600))

    expect(api.edgeTooltipPosition.value).toEqual({ x: 112, y: 212 })
  })

  it('未显示时 mousemove 通过 rAF 合并为一帧更新', () => {
    let pendingFrame: FrameRequestCallback | null = null
    const rafSpy = vi
      .spyOn(window, 'requestAnimationFrame')
      .mockImplementation((cb: FrameRequestCallback) => {
        pendingFrame = cb
        return 1
      })
    const api = useFlowEdgeTooltip({})

    api.onEdgeMouseMove(mouseEvent(300, 400))
    api.onEdgeMouseMove(mouseEvent(350, 450))

    // 同一帧内只排一次回调（第二次移动被 rafId 挡住）
    expect(rafSpy).toHaveBeenCalledTimes(1)

    const frame = pendingFrame as FrameRequestCallback | null
    expect(frame).not.toBeNull()
    frame?.(0)
    expect(api.edgeTooltipPosition.value).toEqual({ x: 312, y: 412 })

    // 帧执行完毕后再次移动可重新排帧
    api.onEdgeMouseMove(mouseEvent(500, 600))
    expect(rafSpy).toHaveBeenCalledTimes(2)

    rafSpy.mockRestore()
  })
})

describe('useFlowEdgeTooltip — 延迟隐藏', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('mouseleave 200ms 后隐藏并清空数据', () => {
    const api = useFlowEdgeTooltip({})
    api.onEdgeMouseEnter(mouseEvent(10, 10))

    api.onEdgeMouseLeave()
    expect(api.edgeTooltipVisible.value).toBe(true)

    vi.advanceTimersByTime(200)

    expect(api.edgeTooltipVisible.value).toBe(false)
    expect(api.edgeTooltipData.value).toBeNull()
  })

  it('悬停到 tooltip 上时取消隐藏计时', () => {
    const api = useFlowEdgeTooltip({})
    api.onEdgeMouseEnter(mouseEvent(10, 10))

    api.onEdgeMouseLeave()
    api.onEdgeTooltipEnter()
    vi.advanceTimersByTime(300)

    expect(api.edgeTooltipVisible.value).toBe(true)
    expect(api.edgeTooltipData.value).not.toBeNull()
  })

  it('离开 tooltip 立即隐藏', () => {
    const api = useFlowEdgeTooltip({})
    api.onEdgeMouseEnter(mouseEvent(10, 10))
    api.onEdgeTooltipEnter()

    api.onEdgeTooltipLeave()

    expect(api.edgeTooltipVisible.value).toBe(false)
    expect(api.edgeTooltipData.value).toBeNull()
  })

  it('mouseleave 时取消挂起的 rAF 位移', () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {})
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation(() => 42)
    const api = useFlowEdgeTooltip({})

    api.onEdgeMouseMove(mouseEvent(10, 10))
    api.onEdgeMouseLeave()

    expect(cancelSpy).toHaveBeenCalledWith(42)
    rafSpy.mockRestore()
    cancelSpy.mockRestore()
  })
})
