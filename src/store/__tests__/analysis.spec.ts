import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { mockTestPointApi } = vi.hoisted(() => ({
  mockTestPointApi: {
    analyze: vi.fn(),
    getList: vi.fn(),
  },
}))

vi.mock('@/api/testPoint', () => ({
  testPointApi: mockTestPointApi,
}))

import { useAnalysisStore } from '../analysis'
import type { TestPoint } from '@/types/testPoint'

// priority 放宽为 number：用于模拟后端返回超出 TestPointPriority(1|2|3) 声明的脏数据
type PointOverrides = Omit<Partial<TestPoint>, 'priority'> & { priority?: number }

function makePoint(overrides: PointOverrides = {}): TestPoint {
  return {
    id: 1,
    project_id: 10,
    module: '登录',
    title: '登录成功',
    priority: 1,
    create_time: '2026-01-01T00:00:00',
    ...overrides,
  } as TestPoint
}

describe('useAnalysisStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  describe('getters', () => {
    it('testPointsByModule: 按 module 分组，缺 module 归入空键', () => {
      const store = useAnalysisStore()
      store.testPoints = [
        makePoint({ id: 1, module: '登录' }),
        makePoint({ id: 2, module: '登录' }),
        makePoint({ id: 3, module: '下单' }),
      ]

      const grouped = store.testPointsByModule

      expect(Object.keys(grouped).sort()).toEqual(['下单', '登录'])
      expect(grouped['登录']).toHaveLength(2)
      expect(grouped['下单']).toHaveLength(1)
    })

    it('testPointsByPriority: 预置 1/2/3 三档，未知优先级动态补键', () => {
      const store = useAnalysisStore()
      store.testPoints = [
        makePoint({ id: 1, priority: 1 }),
        makePoint({ id: 2, priority: 3 }),
        makePoint({ id: 3, priority: 9 }),
      ]

      const grouped = store.testPointsByPriority

      expect(grouped[1]).toHaveLength(1)
      expect(grouped[2]).toHaveLength(0)
      expect(grouped[3]).toHaveLength(1)
      expect(grouped[9]).toHaveLength(1)
    })
  })

  describe('startAnalysis', () => {
    it('成功: 消费异步生成器，进度/消息/测试点逐次更新并置 success', async () => {
      const store = useAnalysisStore()
      mockTestPointApi.analyze.mockReturnValue(
        (async function* () {
          yield { progress: 30, message: '解析需求' }
          yield {
            progress: 100,
            message: '完成',
            data: [makePoint({ id: 7 })],
          }
        })()
      )

      await store.startAnalysis(10)

      expect(mockTestPointApi.analyze).toHaveBeenCalledWith({ project_id: 10 })
      expect(store.currentProjectId).toBe(10)
      expect(store.progress).toBe(100)
      expect(store.status).toBe('success')
      expect(store.message).toBe('分析完成')
      expect(store.testPoints).toHaveLength(1)
      expect(store.testPoints[0].id).toBe(7)
      // create_time 统一转字符串，避免后端返回数字时间戳时模板报错
      expect(typeof store.testPoints[0].create_time).toBe('string')
    })

    it('失败: 异常回落到 failed 状态并给出可执行提示', async () => {
      const store = useAnalysisStore()
      mockTestPointApi.analyze.mockRejectedValueOnce(new Error('deepseek 不可用'))

      await store.startAnalysis(10)

      expect(store.status).toBe('failed')
      expect(store.message).toContain('DeepSeek')
    })
  })

  describe('fetchTestPoints', () => {
    it('成功: 用接口 items 覆盖列表并记录当前项目', async () => {
      const store = useAnalysisStore()
      mockTestPointApi.getList.mockResolvedValueOnce({
        items: [makePoint({ id: 11 }), makePoint({ id: 12 })],
        total: 2,
      })

      await store.fetchTestPoints(10, { module: '登录', priority: 1 })

      expect(mockTestPointApi.getList).toHaveBeenCalledWith(10, { module: '登录', priority: 1 })
      expect(store.testPoints.map((p) => p.id)).toEqual([11, 12])
      expect(store.currentProjectId).toBe(10)
    })

    it('失败: 清空列表且不抛出（页面保留可用状态）', async () => {
      const store = useAnalysisStore()
      store.testPoints = [makePoint({ id: 1 })]
      mockTestPointApi.getList.mockRejectedValueOnce(new Error('网络错误'))

      await expect(store.fetchTestPoints(10)).resolves.toBeUndefined()

      expect(store.testPoints).toEqual([])
    })
  })

  it('resetState: 清空进度、状态、消息、列表与项目上下文', () => {
    const store = useAnalysisStore()
    store.progress = 80
    store.status = 'analyzing'
    store.message = '分析中...'
    store.testPoints = [makePoint()]
    store.currentProjectId = 10

    store.resetState()

    expect(store.progress).toBe(0)
    expect(store.status).toBe('idle')
    expect(store.message).toBe('')
    expect(store.testPoints).toEqual([])
    expect(store.currentProjectId).toBe(0)
  })
})
