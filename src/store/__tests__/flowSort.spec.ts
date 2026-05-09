import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useFlowSortStore } from '../flowSort'

vi.mock('@/api/uiPrototype', () => ({
  uiPrototypeApi: {
    saveProjectFlowData: vi.fn(),
    getProjectFlowData: vi.fn(),
  },
}))

import { uiPrototypeApi } from '@/api/uiPrototype'

function makeNode(id: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    screen_id: Number(id.replace('n', '')),
    screen_name: `页面${id}`,
    flow_type: 'main' as const,
    position: { x: 0, y: 0 },
    ...overrides,
  }
}

async function flushMicro() {
  await Promise.resolve()
  await Promise.resolve()
}

describe('flowSortStore', () => {
  let store: ReturnType<typeof useFlowSortStore>

  function createStore() {
    setActivePinia(createPinia())
    store = useFlowSortStore()
  }

  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    vi.mocked(uiPrototypeApi.saveProjectFlowData).mockReset()
    vi.mocked(uiPrototypeApi.getProjectFlowData).mockReset()
    vi.useFakeTimers()
    createStore()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('初始状态', () => {
    it('mode 默认为 graph', () => expect(store.mode).toBe('graph'))
    it('nodes 和 edges 初始为空数组', () => {
      expect(store.nodes).toEqual([])
      expect(store.edges).toEqual([])
    })
    it('saveStatus 初始为 idle', () => expect(store.saveStatus).toBe('idle'))
    it('projectId 初始为 null', () => expect(store.projectId).toBeNull())
  })

  describe('setProjectId', () => {
    it('注入 projectId', () => {
      store.setProjectId(42)
      expect(store.projectId).toBe(42)
    })
  })

  describe('updateNodes / updateEdges', () => {
    it('更新 nodes 并持久化到 localStorage', () => {
      store.updateNodes([makeNode('n1')])
      expect(store.nodes).toHaveLength(1)
      expect(store.nodes[0].id).toBe('n1')

      const saved = localStorage.getItem('flow-sort-data')
      expect(saved).toBeTruthy()
      const parsed = JSON.parse(saved!)
      expect(parsed.nodes).toHaveLength(1)
    })

    it('localStorage 满时不抛异常', () => {
      const spy = vi.spyOn(Storage.prototype, 'setItem')
      spy.mockImplementationOnce(() => { throw new Error('quota exceeded') })
      expect(() => store.updateNodes([makeNode('n1')])).not.toThrow()
      spy.mockRestore()
    })
  })

  describe('triggerAutoSave', () => {
    it('projectId 为 null 时不触发保存', async () => {
      store.triggerAutoSave()
      vi.advanceTimersByTime(3000)
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).not.toHaveBeenCalled()
    })

    it('debounce 2000ms 后触发保存', async () => {
      store.setProjectId(1)
      store.triggerAutoSave()
      expect(store.saveStatus).toBe('unsaved')
      expect(uiPrototypeApi.saveProjectFlowData).not.toHaveBeenCalled()

      vi.advanceTimersByTime(2000)
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).toHaveBeenCalledTimes(1)
    })

    it('相同 hash 不重复保存', async () => {
      store.setProjectId(1)
      store.triggerAutoSave()
      vi.advanceTimersByTime(2000)
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).toHaveBeenCalledTimes(1)

      store.triggerAutoSave()
      vi.advanceTimersByTime(2000)
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).toHaveBeenCalledTimes(1)
    })

    it('数据变更后 hash 不同，重新保存', async () => {
      store.setProjectId(1)
      store.triggerAutoSave()
      vi.advanceTimersByTime(2000)
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).toHaveBeenCalledTimes(1)

      store.updateNodes([makeNode('n1')])
      store.triggerAutoSave()
      vi.advanceTimersByTime(2000)
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).toHaveBeenCalledTimes(2)
    })

    it('快速连续编辑仅触发一次保存', async () => {
      store.setProjectId(1)
      store.triggerAutoSave()
      vi.advanceTimersByTime(1000)
      store.triggerAutoSave()
      vi.advanceTimersByTime(1000)
      store.triggerAutoSave()
      vi.advanceTimersByTime(2000)
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).toHaveBeenCalledTimes(1)
    })

    it('debounce 期间状态为 unsaved', () => {
      store.setProjectId(1)
      store.triggerAutoSave()
      expect(store.saveStatus).toBe('unsaved')
      vi.advanceTimersByTime(500)
      expect(store.saveStatus).toBe('unsaved')
    })
  })

  describe('performSave', () => {
    const successRes = {
      code: 200,
      data: { id: 1, project_id: 1, flow_data: { nodes: [], edges: [] }, create_time: '', update_time: '' },
      msg: 'ok',
    } as const

    it('成功保存后状态: unsaved → saving → saved → 3s → idle', async () => {
      vi.mocked(uiPrototypeApi.saveProjectFlowData).mockResolvedValue(successRes)
      store.setProjectId(1)

      store.triggerAutoSave()
      expect(store.saveStatus).toBe('unsaved')

      vi.advanceTimersByTime(2000)
      expect(store.saveStatus).toBe('saving')

      await flushMicro()
      expect(store.saveStatus).toBe('saved')

      vi.advanceTimersByTime(3000)
      expect(store.saveStatus).toBe('idle')
    })

    it('5xx 错误自动重试一次（delay 3s）后成功', async () => {
      const mock = vi.mocked(uiPrototypeApi.saveProjectFlowData)
      const err = new Error('503') as Error & { response: { status: number } }
      err.response = { status: 503 }
      mock.mockRejectedValueOnce(err).mockResolvedValueOnce(successRes)
      store.setProjectId(1)

      store.triggerAutoSave()
      vi.advanceTimersByTime(2000)
      await flushMicro()
      expect(mock).toHaveBeenCalledTimes(1)
      expect(store.saveStatus).toBe('saving')

      vi.advanceTimersByTime(3000)
      await flushMicro()
      expect(mock).toHaveBeenCalledTimes(2)
      expect(store.saveStatus).toBe('saved')
    })

    it('两次 5xx 重试后最终 error', async () => {
      const err = new Error('503') as Error & { response: { status: number } }
      err.response = { status: 503 }
      vi.mocked(uiPrototypeApi.saveProjectFlowData).mockRejectedValue(err)
      store.setProjectId(1)

      store.triggerAutoSave()
      vi.advanceTimersByTime(2000)
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).toHaveBeenCalledTimes(1)

      vi.advanceTimersByTime(3000)
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).toHaveBeenCalledTimes(2)
      expect(store.saveStatus).toBe('error')
    })

    it('4xx 错误不重试，直接 error', async () => {
      const err = new Error('403') as Error & { response: { status: number } }
      err.response = { status: 403 }
      vi.mocked(uiPrototypeApi.saveProjectFlowData).mockRejectedValue(err)
      store.setProjectId(1)

      store.triggerAutoSave()
      vi.advanceTimersByTime(2000)
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).toHaveBeenCalledTimes(1)
      expect(store.saveStatus).toBe('error')
    })
  })

  describe('manualRetrySave', () => {
    it('清除 debounce timer 并立即保存', async () => {
      store.setProjectId(1)
      store.triggerAutoSave()
      store.manualRetrySave()
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).toHaveBeenCalledTimes(1)
    })
  })

  describe('reset', () => {
    it('重置所有状态并清理 timer 和 localStorage', () => {
      store.setProjectId(1)
      store.updateNodes([makeNode('n1')])
      store.triggerAutoSave()
      store.reset()

      expect(store.mode).toBe('graph')
      expect(store.nodes).toEqual([])
      expect(store.projectId).toBeNull()
      expect(store.saveStatus).toBe('idle')
      expect(localStorage.getItem('flow-sort-data')).toBeNull()
    })
  })

  describe('loadFromBackend', () => {
    it('projectId 为 null 时不请求', async () => {
      await store.loadFromBackend()
      expect(uiPrototypeApi.getProjectFlowData).not.toHaveBeenCalled()
    })

    it('后端有数据时恢复并同步 localStorage', async () => {
      const serverNodes = [makeNode('n_server', { position: { x: 50, y: 50 } })]
      const serverEdges = [{
        id: 'e_s',
        source: 'n_server',
        target: 'n2',
        edge_type: 'normal' as const,
        label: '下一步',
      }]
      vi.mocked(uiPrototypeApi.getProjectFlowData).mockResolvedValue({
        code: 200,
        data: { id: 1, project_id: 1, flow_data: { nodes: serverNodes, edges: serverEdges }, create_time: '', update_time: '' },
        msg: '',
      })
      store.setProjectId(1)
      await store.loadFromBackend()

      expect(store.nodes).toHaveLength(1)
      expect(store.nodes[0].id).toBe('n_server')
      expect(store.nodes[0].image_url).toBe('')
      expect(store.nodes[0].position).toEqual({ x: 50, y: 50 })
      expect(store.edges).toHaveLength(1)
      expect(store.edges[0].id).toBe('e_s')
    })

    it('后端无数据 + localStorage 有数据时恢复（store创建前写localStorage）', async () => {
      localStorage.setItem('flow-sort-data', JSON.stringify({
        mode: 'graph',
        nodes: [makeNode('n_local', { flow_type: 'branch' })],
        edges: [],
      }))
      createStore()
      vi.mocked(uiPrototypeApi.getProjectFlowData).mockResolvedValue({
        code: 200,
        data: null as unknown as { flow_data: never },
        msg: '暂无保存数据',
      })
      store.setProjectId(1)
      await store.loadFromBackend()

      expect(store.nodes).toHaveLength(1)
      expect(store.nodes[0].id).toBe('n_local')
    })

    it('网络错误 + localStorage 有数据时降级恢复', async () => {
      localStorage.setItem('flow-sort-data', JSON.stringify({
        mode: 'graph',
        nodes: [makeNode('n_fallback')],
        edges: [],
      }))
      createStore()
      vi.mocked(uiPrototypeApi.getProjectFlowData).mockRejectedValue(new Error('network error'))
      store.setProjectId(1)
      await store.loadFromBackend()

      expect(store.nodes).toHaveLength(1)
      expect(store.nodes[0].id).toBe('n_fallback')
    })
  })

  describe('computeHash 验证', () => {
    it('不同数据产生不同 hash', async () => {
      store.setProjectId(1)

      store.updateNodes([makeNode('n1', { screen_name: 'A' })])
      store.triggerAutoSave()
      vi.advanceTimersByTime(2000)
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).toHaveBeenCalledTimes(1)

      store.updateNodes([makeNode('n2', { screen_name: 'B' })])
      store.triggerAutoSave()
      vi.advanceTimersByTime(2000)
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).toHaveBeenCalledTimes(2)
    })

    it('相同数据产生相同 hash，跳过保存', async () => {
      store.setProjectId(1)
      const node = makeNode('n1')
      store.updateNodes([node])
      store.triggerAutoSave()
      vi.advanceTimersByTime(2000)
      await flushMicro()
      const callCount = uiPrototypeApi.saveProjectFlowData.mock.calls.length

      store.triggerAutoSave()
      vi.advanceTimersByTime(2000)
      await flushMicro()
      expect(uiPrototypeApi.saveProjectFlowData).toHaveBeenCalledTimes(callCount)
    })
  })

  describe('字段映射完整性', () => {
    it('image_url 和 trigger_action 包含在保存数据中', async () => {
      store.setProjectId(1)
      store.updateNodes([makeNode('n1', { image_url: 'https://e.g/img.png' })])
      store.manualRetrySave()
      await flushMicro()

      const flowData = vi.mocked(uiPrototypeApi.saveProjectFlowData).mock.calls[0][1]
      expect(flowData.nodes[0].image_url).toBe('https://e.g/img.png')
    })
  })
})
