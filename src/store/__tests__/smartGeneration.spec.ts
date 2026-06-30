import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick } from 'vue'

const { warningMock } = vi.hoisted(() => ({ warningMock: vi.fn() }))

vi.mock('element-plus', () => ({
  ElMessage: { warning: warningMock, error: vi.fn(), success: vi.fn(), info: vi.fn() },
}))
vi.mock('@/api/generationBatch', () => ({
  generationBatchApi: { create: vi.fn(), update: vi.fn(), save: vi.fn() },
}))
vi.mock('@/api/case/ai', () => ({ aiApi: { generateContext: vi.fn() } }))
vi.mock('@/api/aiInvocation', () => ({ aiInvocationApi: { getBatchCost: vi.fn() } }))
vi.mock('@/api/uiPrototype', () => ({
  uiPrototypeApi: {
    getUIPrototypeProjectList: vi.fn(),
    getUIScreenList: vi.fn(),
    parseUIScreens: vi.fn(),
    uploadUIScreens: vi.fn(),
  },
}))
vi.mock('@/api/historyAsset', () => ({
  historyAssetApi: {
    getList: vi.fn(),
    upload: vi.fn(),
    importSystemCases: vi.fn(),
    align: vi.fn(),
  },
}))

import { useSmartGenerationStore } from '../smartGeneration'
import { uiPrototypeApi } from '@/api/uiPrototype'

/** 构造简易 JWT，payload 由参数指定 */
function makeJwt(payload: Record<string, unknown>): string {
  const b64 = (obj: unknown) =>
    btoa(JSON.stringify(obj)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${b64({ alg: 'HS256' })}.${b64(payload)}.sig`
}

function sseLine(obj: unknown): string {
  return `data: ${JSON.stringify(obj)}`
}

/** 构造一次性 SSE 响应：依次返回 chunks，结束后 done */
function makeSseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  let i = 0
  const reader = {
    read: async () => {
      if (i < chunks.length) {
        const value = encoder.encode(chunks[i])
        i++
        return { done: false, value }
      }
      return { done: true, value: undefined as unknown as Uint8Array }
    },
  }
  return { body: { getReader: () => reader } } as unknown as Response
}

/** 构造挂起响应：先返回一个 chunk，随后 read 挂起，signal abort 时拒绝 AbortError */
function makeHangAfterChunkResponse(chunk: string, signal?: AbortSignal | null): Response {
  const encoder = new TextEncoder()
  let sent = false
  const reader = {
    read: () =>
      new Promise<unknown>((resolve, reject) => {
        if (!sent) {
          sent = true
          resolve({ done: false, value: encoder.encode(chunk) })
          return
        }
        const err = Object.assign(new Error('aborted'), { name: 'AbortError' })
        if (signal?.aborted) {
          reject(err)
          return
        }
        signal?.addEventListener('abort', () => reject(err), { once: true })
      }),
  }
  return { body: { getReader: () => reader } } as unknown as Response
}

function makeContext(testPoints: Record<string, unknown>[] = [{ id: 1 }]) {
  return {
    requirement_content: '需求',
    ui_descriptions: [] as string[],
    ui_specs: [] as string[],
    test_points: testPoints,
    history_cases: [] as Record<string, unknown>[],
    context_stats: {},
    warnings: [],
    evidence_refs: {},
    project_config: {},
  }
}

function caseEvent(title: string, tpId = 1): string {
  return sseLine({
    code: 0,
    data: {
      title,
      test_point_id: tpId,
      module: 'm',
      precondition: 'p',
      steps: [{ step: 1, action: 'a', expected_result: 'e' }],
      expected_result: '预期',
      priority: 3,
      case_type: 'manual',
    },
  })
}

async function flushMicro(times = 10): Promise<void> {
  for (let i = 0; i < times; i++) await Promise.resolve()
}

let store: ReturnType<typeof useSmartGenerationStore>

beforeEach(() => {
  localStorage.clear()
  warningMock.mockReset()
  vi.mocked(uiPrototypeApi.getUIScreenList).mockReset()
  vi.mocked(uiPrototypeApi.parseUIScreens).mockReset()
  setActivePinia(createPinia())
  store = useSmartGenerationStore()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Task1: 主路径与重生成路径统一读取 advancedConfig', () => {
  it('主路径 fetch body 读取 advancedConfig（非写死 linear/priority=2）', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(makeSseResponse([]))
    store.generationContext = makeContext()
    store.advancedConfig = {
      case_type: 'api',
      exec_mode: 'auto',
      priority: 5,
      enhanced_mode: false,
      mode: 'graph',
    }

    await store.startGeneration()

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    const init = fetchSpy.mock.calls[0][1] as RequestInit
    const body = JSON.parse(init.body as string) as Record<string, unknown>
    expect(body.case_type).toBe('api')
    expect(body.exec_mode).toBe('auto')
    expect(body.priority).toBe(5)
    expect(body.enhanced_mode).toBe(false)
    expect(body.mode).toBe('graph')
  })

  it('priority 默认值 2 保留：advancedConfig 未改时主路径传 2', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(makeSseResponse([]))
    store.generationContext = makeContext()
    // advancedConfig 保持初始默认（priority=2）

    await store.startGeneration()

    const init = vi.mocked(globalThis.fetch).mock.calls[0][1] as RequestInit
    const body = JSON.parse(init.body as string) as Record<string, unknown>
    expect(body.priority).toBe(2)
    expect(body.mode).toBe('linear')
  })

  it('重生成路径 fetch body 同样读取 advancedConfig（来源一致）', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(makeSseResponse([]))
    store.generationContext = makeContext()
    store.advancedConfig = {
      case_type: 'api',
      exec_mode: 'auto',
      priority: 9,
      enhanced_mode: false,
      mode: 'graph',
    }
    store.previewCases = [
      {
        client_id: 'c1',
        source_test_point_id: 7,
        requirement_file_id: null,
        title: 't',
        module: 'm',
        precondition: 'p',
        steps: [],
        expected_result: 'e',
        priority: 3,
        case_type: 'manual',
        case_category: null,
        quality_status: 'pending_review',
        quality_issues: [],
        selected_for_save: true,
        dirty: false,
        regenerating: false,
        source_refs: {},
      },
    ]

    await store.regenerateSingleCase('c1')

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    const init = fetchSpy.mock.calls[0][1] as RequestInit
    const body = JSON.parse(init.body as string) as Record<string, unknown>
    // advancedConfig 字段一致
    expect(body.case_type).toBe('api')
    expect(body.exec_mode).toBe('auto')
    expect(body.enhanced_mode).toBe(false)
    expect(body.mode).toBe('graph')
    // priority 取原用例
    expect(body.priority).toBe(3)
    expect(body.test_point_id).toBe(7)
  })
})

describe('Task3.1: SSE 进度跟踪 progressPercent', () => {
  it('首个 SSE 事件 total 校正总数，已生成/总数 得到百分比', async () => {
    const chunk =
      [
        sseLine({ code: 0, data: { status: 'started', total: 4 } }),
        caseEvent('c1'),
        caseEvent('c2'),
      ].join('\n') + '\n'
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(makeSseResponse([chunk]))
    store.generationContext = makeContext([])

    await store.startGeneration()

    expect(store.sseTotalCount).toBe(4)
    expect(store.previewCases.length).toBe(2)
    expect(store.progressPercent).toBe(50)
  })

  it('上下文测试点数作为总数回退（SSE 未携带 total）', async () => {
    const chunk =
      [sseLine({ code: 0, data: { status: 'started' } }), caseEvent('c1')].join('\n') + '\n'
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(makeSseResponse([chunk]))
    store.generationContext = makeContext([{ id: 1 }, { id: 2 }, { id: 3 }])

    await store.startGeneration()

    expect(store.sseTotalCount).toBe(3)
    expect(store.progressPercent).toBe(33)
  })

  it('总数未知时降级为 null（indeterminate 边界）', async () => {
    const chunk =
      [sseLine({ code: 0, data: { status: 'started' } }), caseEvent('c1')].join('\n') + '\n'
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(makeSseResponse([chunk]))
    store.generationContext = makeContext([]) // 无测试点

    await store.startGeneration()

    expect(store.sseTotalCount).toBe(0)
    expect(store.progressPercent).toBeNull()
  })
})

describe('Task4.1: AbortController 真中断', () => {
  it('主路径 fetch 收到 signal；abort 后中断并保留已生成部分用例', async () => {
    let capturedSignal: AbortSignal | null | undefined
    const chunk = caseEvent('c1') + '\n'
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) => {
      capturedSignal = (init as RequestInit | undefined)?.signal
      return makeHangAfterChunkResponse(chunk, capturedSignal)
    })
    store.generationContext = makeContext([{ id: 1 }])

    const p = store.startGeneration()
    // 等待首个 case 被处理后再中断
    await vi.waitFor(() => expect(store.previewCases.length).toBe(1))
    store.abortGeneration()
    await p

    expect(capturedSignal?.aborted).toBe(true)
    expect(store.generating).toBe(false)
    expect(store.generationProgress).toBe('已取消生成')
    // 已生成部分用例保留
    expect(store.previewCases.length).toBe(1)
  })

  it('中断不标记批次失败、不抛错（batchId 为空时 batchStatus 不变）', async () => {
    let capturedSignal: AbortSignal | null | undefined
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) => {
      capturedSignal = (init as RequestInit | undefined)?.signal
      return makeHangAfterChunkResponse('', capturedSignal)
    })
    store.generationContext = makeContext()

    const p = store.startGeneration()
    await flushMicro()
    store.abortGeneration()
    await p

    expect(store.generating).toBe(false)
    expect(store.batchStatus).not.toBe('failed')
  })

  it('重生成路径中断后保留原用例且不抛错', async () => {
    let capturedSignal: AbortSignal | null | undefined
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) => {
      capturedSignal = (init as RequestInit | undefined)?.signal
      return makeHangAfterChunkResponse('', capturedSignal)
    })
    store.generationContext = makeContext()
    store.previewCases = [
      {
        client_id: 'c1',
        source_test_point_id: 1,
        requirement_file_id: null,
        title: 't',
        module: 'm',
        precondition: 'p',
        steps: [],
        expected_result: 'e',
        priority: 2,
        case_type: 'manual',
        case_category: null,
        quality_status: 'passed',
        quality_issues: [],
        selected_for_save: true,
        dirty: false,
        regenerating: false,
        source_refs: {},
      },
    ]

    await expect(
      (async () => {
        const p = store.regenerateSingleCase('c1')
        await flushMicro()
        store.abortGeneration()
        await p
      })()
    ).resolves.toBeUndefined()
    // 原用例保留
    expect(store.previewCases.length).toBe(1)
    expect(store.previewCases[0].title).toBe('t')
  })
})

describe('Task6.2: UI 截图批量请求', () => {
  it('N+1 串行改为单次批量调用，返回 {id:url} 映射', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ '1': '/img/1.png', '2': '/img/2.png' }),
    } as unknown as Response)
    store.uiScreenDetails = [
      { id: 1, original_file_path: '/a.png' } as never,
      { id: 2, original_file_path: '/b.png' } as never,
    ]

    await store.loadUIScreenImages()

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    const url = String(fetchSpy.mock.calls[0][0])
    expect(url).toContain('/api/v1/ui-screens/batch?ids=1,2')
    expect(store.uiScreenImageUrls[1]).toBe('/img/1.png')
    expect(store.uiScreenImageUrls[2]).toBe('/img/2.png')
  })

  it('兼容 {code,data:{id:url}} 包装结构', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ code: 0, data: { '5': '/img/5.png' } }),
    } as unknown as Response)
    store.uiScreenDetails = [{ id: 5, original_file_path: '/c.png' } as never]

    await store.loadUIScreenImages()

    expect(store.uiScreenImageUrls[5]).toBe('/img/5.png')
  })

  it('已加载的截图不重复请求（幂等）', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ '1': '/img/1.png' }),
    } as unknown as Response)
    store.uiScreenDetails = [{ id: 1, original_file_path: '/a.png' } as never]

    await store.loadUIScreenImages()
    await store.loadUIScreenImages()

    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('无待加载截图时直接返回（空值边界）', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    store.uiScreenDetails = []
    await store.loadUIScreenImages()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('批量请求失败时保持空，不抛错（异常边界）', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network'))
    store.uiScreenDetails = [{ id: 1, original_file_path: '/a.png' } as never]
    await expect(store.loadUIScreenImages()).resolves.toBeUndefined()
    expect(store.uiScreenImageUrls[1]).toBeUndefined()
  })
})

describe('Task7: UI 解析超时提示', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('3 分钟（60 次轮询）超时后弹 warning 并置 uiParsing=timeout', async () => {
    vi.mocked(uiPrototypeApi.parseUIScreens).mockResolvedValue({
      task_id: 't',
      screen_ids: [10],
      message: '',
    } as never)
    // 持续返回 pending，永不完成
    vi.mocked(uiPrototypeApi.getUIScreenList).mockResolvedValue([
      { id: 10, parse_status: 'pending' },
    ] as never)
    store.selectedProjectId = 1

    await store.parseUIScreens([10])
    // 推进 60 次轮询（60 * 3000ms）
    await vi.advanceTimersByTimeAsync(60 * 3000)

    expect(warningMock).toHaveBeenCalledWith('UI 解析超时，请稍后重试或检查 UI 文件')
    expect(store.uiParsing).toBe('timeout')
  })

  it('解析完成时 uiParsing 置回 false，不弹超时', async () => {
    vi.mocked(uiPrototypeApi.parseUIScreens).mockResolvedValue({
      task_id: 't',
      screen_ids: [11],
      message: '',
    } as never)
    vi.mocked(uiPrototypeApi.getUIScreenList).mockResolvedValue([
      { id: 11, parse_status: 'completed' },
    ] as never)
    store.selectedProjectId = 1

    await store.parseUIScreens([11])
    await vi.advanceTimersByTimeAsync(3000)

    expect(warningMock).not.toHaveBeenCalled()
    expect(store.uiParsing).toBe(false)
  })
})

describe('Task10: 用户偏好记忆', () => {
  it('字段变更后自动持久化到 smart-gen:{userId}:pref', async () => {
    localStorage.setItem('token', makeJwt({ sub: 'userA' }))
    store.selectedProjectId = 5
    store.selectedTask = 'history_update'
    store.advancedConfig = {
      ...store.advancedConfig,
      case_type: 'api',
      exec_mode: 'auto',
      enhanced_mode: false,
      mode: 'graph',
    }
    await nextTick()

    const raw = localStorage.getItem('smart-gen:userA:pref') || ''
    expect(raw).toContain('"selectedProjectId":5')
    expect(raw).toContain('"selectedTask":"history_update"')
    expect(raw).toContain('"mode":"graph"')
    expect(raw).toContain('"enhanced_mode":false')
    expect(raw).not.toContain('token')
  })

  it('restorePreference 恢复上次偏好（关闭重进场景）', async () => {
    localStorage.setItem('token', makeJwt({ sub: 'userA' }))
    store.selectedProjectId = 7
    store.selectedTask = 'import_asset'
    store.advancedConfig = { ...store.advancedConfig, mode: 'graph', case_type: 'api' }
    await nextTick()

    // 全新 store 实例模拟重新进入页面
    setActivePinia(createPinia())
    const fresh = useSmartGenerationStore()
    localStorage.setItem('token', makeJwt({ sub: 'userA' }))
    fresh.restorePreference()

    expect(fresh.selectedProjectId).toBe(7)
    expect(fresh.selectedTask).toBe('import_asset')
    expect(fresh.advancedConfig.mode).toBe('graph')
    expect(fresh.advancedConfig.case_type).toBe('api')
  })

  it('按 userId 隔离：userB 无 userA 的偏好', async () => {
    localStorage.setItem('token', makeJwt({ sub: 'userA' }))
    store.selectedProjectId = 9
    await nextTick()
    expect(localStorage.getItem('smart-gen:userA:pref')).not.toBeNull()

    setActivePinia(createPinia())
    const other = useSmartGenerationStore()
    localStorage.setItem('token', makeJwt({ sub: 'userB' }))
    other.restorePreference()

    expect(other.selectedProjectId).toBe('')
    expect(other.advancedConfig.mode).toBe('linear')
  })

  it('无偏好记录时 restorePreference 静默跳过（空值边界）', () => {
    localStorage.setItem('token', makeJwt({ sub: 'newUser' }))
    expect(() => store.restorePreference()).not.toThrow()
    expect(store.selectedProjectId).toBe('')
    expect(store.advancedConfig.mode).toBe('linear')
  })

  it('reset 不清空已持久化偏好（重新开始不丢记忆）', async () => {
    localStorage.setItem('token', makeJwt({ sub: 'userA' }))
    store.selectedProjectId = 12
    store.advancedConfig = { ...store.advancedConfig, mode: 'graph' }
    await nextTick()
    const before = localStorage.getItem('smart-gen:userA:pref')

    store.reset()
    await nextTick()

    expect(localStorage.getItem('smart-gen:userA:pref')).toBe(before)
    expect(store.selectedProjectId).toBe('')
  })
})

describe('Task8.2: 错误提示透出真实原因', () => {
  it('主路径生成失败透出后端 detail 而非通用文案', async () => {
    const detail = { response: { data: { detail: 'test_points 字段不能为空' } } }
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(detail)
    store.generationContext = makeContext()
    store.batchId = null

    await store.startGeneration()

    expect(store.generationProgress).toBe('test_points 字段不能为空')
    expect(store.batchStatus).not.toBe('failed')
  })
})
