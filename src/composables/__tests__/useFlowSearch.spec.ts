import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { ref } from 'vue'
import { useFlowSearch } from '../useFlowSearch'
import type { FlowEditorNode } from '../useFlowEditor'

function node(id: string, name: string, summary = '', flowType = 'main'): FlowEditorNode {
  return {
    id,
    data: { screen_name: name, summary, flow_type: flowType },
  } as unknown as FlowEditorNode
}

function setup() {
  const vueFlowNodes = ref<FlowEditorNode[]>([
    node('n1', '登录页', '账号密码登录'),
    node('n2', '首页', '展示工作台'),
    node('n3', 'Login-Success', ''),
  ])
  const fitView = vi.fn()
  const api = useFlowSearch({
    vueFlowNodes,
    getNodeData: (n) => n.data as never,
    fitView,
  })
  return { api, vueFlowNodes, fitView }
}

describe('useFlowSearch — 结果匹配', () => {
  it('空关键词返回空结果', () => {
    const { api } = setup()
    api.searchKeyword.value = '   '

    expect(api.searchResults.value).toEqual([])
  })

  it('按 screen_name 大小写不敏感匹配', () => {
    const { api } = setup()
    api.searchKeyword.value = 'login'

    expect(api.searchResults.value.map((r) => r.id)).toEqual(['n3'])
  })

  it('按 summary 匹配并返回精简结构', () => {
    const { api } = setup()
    api.searchKeyword.value = '登录'

    expect(api.searchResults.value).toEqual([
      { id: 'n1', screen_name: '登录页', flow_type: 'main' },
    ])
  })

  it('无命中返回空数组', () => {
    const { api } = setup()
    api.searchKeyword.value = '下单'

    expect(api.searchResults.value).toEqual([])
  })
})

describe('useFlowSearch — 定位与清理', () => {
  it('locateNode 高亮并适配视图', () => {
    const { api, fitView } = setup()

    api.locateNode('n2')

    expect(api.searchMatchIds.value).toEqual(['n2'])
    expect(api.showSearchDropdown.value).toBe(false)
    expect(fitView).toHaveBeenCalledWith({ nodes: ['n2'], duration: 300, padding: 0.3 })
  })

  it('locateFirstMatch 无结果时不动作，有结果时定位首个', () => {
    const { api, fitView } = setup()

    api.locateFirstMatch()
    expect(fitView).not.toHaveBeenCalled()

    api.searchKeyword.value = '登录'
    api.locateFirstMatch()
    expect(api.searchMatchIds.value).toEqual(['n1'])
  })

  it('clearSearch 清空匹配与下拉', () => {
    const { api } = setup()
    api.searchMatchIds.value = ['n1']
    api.showSearchDropdown.value = true

    api.clearSearch()

    expect(api.searchMatchIds.value).toEqual([])
    expect(api.showSearchDropdown.value).toBe(false)
  })
})

describe('useFlowSearch — 防抖与失焦', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('300ms 后批量写入匹配并定位首个结果', () => {
    const { api, fitView } = setup()
    api.searchKeyword.value = '登录'

    api.debouncedSearch()
    expect(api.searchMatchIds.value).toEqual([])

    vi.advanceTimersByTime(300)

    expect(api.searchMatchIds.value).toEqual(['n1'])
    // 命中后立即定位首个结果，locateNode 会把下拉收起
    expect(api.showSearchDropdown.value).toBe(false)
    expect(fitView).toHaveBeenCalledTimes(1)
  })

  it('空关键词在防抖结束后仅清空匹配', () => {
    const { api, fitView } = setup()
    api.searchKeyword.value = '   '

    api.debouncedSearch()
    vi.advanceTimersByTime(300)

    expect(api.searchMatchIds.value).toEqual([])
    expect(fitView).not.toHaveBeenCalled()
  })

  it('连续输入只执行最后一次', () => {
    const { api, fitView } = setup()
    api.searchKeyword.value = '登录'

    api.debouncedSearch()
    vi.advanceTimersByTime(200)
    api.debouncedSearch()
    vi.advanceTimersByTime(300)

    expect(fitView).toHaveBeenCalledTimes(1)
  })

  it('失焦 200ms 后关闭下拉', () => {
    const { api } = setup()
    api.showSearchDropdown.value = true

    api.handleSearchBlur()
    expect(api.showSearchDropdown.value).toBe(true)

    vi.advanceTimersByTime(200)
    expect(api.showSearchDropdown.value).toBe(false)
  })
})
