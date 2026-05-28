import { describe, expect, it } from 'vitest'
import { hasActiveUiFlow } from '../generateHelpers'
import type { GenerateState } from '../state'
import { ref, reactive } from 'vue'

function makeState(
  overrides: Partial<{
    selectedUiPrototypeProjectId: number | ''
    uiScreenIds: number[]
    uiScreensCount: number
  }> = {}
): GenerateState {
  return {
    selectedUiPrototypeProjectId: ref(overrides.selectedUiPrototypeProjectId ?? 1),
    formData: reactive({ ui_screen_ids: overrides.uiScreenIds ?? [1, 2] }),
    uiScreens: ref(
      Array.from({ length: overrides.uiScreensCount ?? 2 }, (_, i) => ({ id: i + 1 }))
    ),
  } as unknown as GenerateState
}

function makeFlowSortStore(
  overrides: Partial<{
    quickMode: boolean
    nodesCount: number
  }> = {}
) {
  return {
    quickMode: overrides.quickMode ?? true,
    nodes: Array.from({ length: overrides.nodesCount ?? 0 }, (_, i) => ({ id: i })),
  }
}

describe('hasActiveUiFlow', () => {
  it('快速模式(quickMode=true)始终返回 false', () => {
    const state = makeState()
    const store = makeFlowSortStore({ quickMode: true, nodesCount: 3 })
    expect(hasActiveUiFlow(state, store)).toBe(false)
  })

  it('编辑模式(quickMode=false)且有 UI 流程数据时返回 true', () => {
    const state = makeState()
    const store = makeFlowSortStore({ quickMode: false, nodesCount: 3 })
    expect(hasActiveUiFlow(state, store)).toBe(true)
  })

  it('编辑模式但无 selectedUiPrototypeProjectId 时返回 false', () => {
    const state = makeState({ selectedUiPrototypeProjectId: '' })
    const store = makeFlowSortStore({ quickMode: false, nodesCount: 3 })
    expect(hasActiveUiFlow(state, store)).toBe(false)
  })

  it('编辑模式但 ui_screen_ids 为空时返回 false', () => {
    const state = makeState({ uiScreenIds: [] })
    const store = makeFlowSortStore({ quickMode: false, nodesCount: 3 })
    expect(hasActiveUiFlow(state, store)).toBe(false)
  })

  it('编辑模式且 nodes 为空但 uiScreens 有数据时返回 true', () => {
    const state = makeState({ uiScreensCount: 2 })
    const store = makeFlowSortStore({ quickMode: false, nodesCount: 0 })
    expect(hasActiveUiFlow(state, store)).toBe(true)
  })

  it('编辑模式且 nodes 和 uiScreens 都为空时返回 false', () => {
    const state = makeState({ uiScreensCount: 0 })
    const store = makeFlowSortStore({ quickMode: false, nodesCount: 0 })
    expect(hasActiveUiFlow(state, store)).toBe(false)
  })

  it('快速模式即使所有条件满足也返回 false', () => {
    const state = makeState()
    const store = makeFlowSortStore({ quickMode: true, nodesCount: 10 })
    expect(hasActiveUiFlow(state, store)).toBe(false)
  })
})
