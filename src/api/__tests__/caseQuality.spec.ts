import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import requestDefault from '@/utils/request'
import {
    triggerPosteriorScoring,
    getPosteriorResult,
    type PosteriorResult,
    type PosteriorStats,
} from '@/api/caseQuality'

// Mock request 工具：caseQuality.ts 通过 `import request from '@/utils/request'` 使用 axios 实例的 post/get 方法。
// 响应拦截器已将 axios 原始 AxiosResponse 解包为 ApiResponse 形态，故此处按实际 resolve 值类型断言以获得类型安全。
interface ApiResponseData<T> {
    code: number
    message: string
    data: T
}

vi.mock('@/utils/request', () => ({
    default: {
        post: vi.fn(),
        get: vi.fn(),
    },
}))

const request = requestDefault as unknown as {
    post: (url: string) => Promise<ApiResponseData<PosteriorResult>>
    get: (url: string) => Promise<ApiResponseData<PosteriorStats>>
}
const postMock = vi.mocked(request.post)
const getMock = vi.mocked(request.get)

function makePosteriorResult(overrides: Partial<PosteriorResult> = {}): PosteriorResult {
    return {
        project_id: 1,
        posterior_quality_score: 88.5,
        review_pass_rate: 0.9,
        execution_pass_rate: 0.8,
        modification_rate: 0.2,
        total_reviewed: 10,
        total_executed: 8,
        total_cases: 12,
        meets_min_executions: true,
        ...overrides,
    }
}

function makePosteriorStats(overrides: Partial<PosteriorStats> = {}): PosteriorStats {
    return {
        project_id: 1,
        avg_posterior_score: 85.5,
        max_posterior_score: 95,
        min_posterior_score: 70,
        total_cases: 12,
        scored_cases: 10,
        unscored_cases: 2,
        distribution: { A_90_100: 3, B_75_89: 4, C_60_74: 2, D_0_59: 1 },
        ...overrides,
    }
}

describe('caseQuality API - triggerPosteriorScoring', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    it('以 POST 方法调用正确路径 /api/v1/quality/posterior/{projectId}', async () => {
        postMock.mockResolvedValueOnce({
            code: 0,
            message: 'success',
            data: makePosteriorResult(),
        })

        await triggerPosteriorScoring(1)

        // 验证方法（post）与路径：仅传 URL 一个参数，后端不接收 body
        expect(postMock).toHaveBeenCalledTimes(1)
        expect(postMock).toHaveBeenCalledWith('/api/v1/quality/posterior/1')
        expect(getMock).not.toHaveBeenCalled()
    })

    it('projectId 被正确拼接到 URL 路径', async () => {
        postMock.mockResolvedValueOnce({
            code: 0,
            message: 'success',
            data: makePosteriorResult({ project_id: 42 }),
        })

        await triggerPosteriorScoring(42)

        expect(postMock).toHaveBeenCalledWith('/api/v1/quality/posterior/42')
    })

    it('成功时返回包含 PosteriorResult 的响应', async () => {
        const result = makePosteriorResult()
        postMock.mockResolvedValueOnce({ code: 0, message: 'success', data: result })

        const res = await triggerPosteriorScoring(1)

        expect(res.code).toBe(0)
        expect(res.data).toEqual(result)
        expect(res.data.posterior_quality_score).toBe(88.5)
        expect(res.data.meets_min_executions).toBe(true)
    })

    it('执行样本不足时 meets_min_executions 为 false 仍正常返回', async () => {
        // 边界场景：样本不足，结果仅供参考
        postMock.mockResolvedValueOnce({
            code: 0,
            message: 'success',
            data: makePosteriorResult({ meets_min_executions: false, total_executed: 1 }),
        })

        const res = await triggerPosteriorScoring(1)

        expect(res.data.meets_min_executions).toBe(false)
        expect(res.data.total_executed).toBe(1)
    })

    it('请求失败（如 500 后验评分计算失败）时抛出异常', async () => {
        postMock.mockRejectedValueOnce(new Error('后验质量评分计算失败'))

        await expect(triggerPosteriorScoring(1)).rejects.toThrow('后验质量评分计算失败')
        expect(postMock).toHaveBeenCalledWith('/api/v1/quality/posterior/1')
    })

    it('项目不存在（404）时抛出异常', async () => {
        postMock.mockRejectedValueOnce(new Error('项目不存在'))

        await expect(triggerPosteriorScoring(999)).rejects.toThrow('项目不存在')
        expect(postMock).toHaveBeenCalledWith('/api/v1/quality/posterior/999')
    })
})

describe('caseQuality API - getPosteriorResult', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    it('以 GET 方法调用正确路径 /api/v1/quality/posterior/{projectId}/result', async () => {
        getMock.mockResolvedValueOnce({
            code: 0,
            message: 'success',
            data: makePosteriorStats(),
        })

        await getPosteriorResult(1)

        // 验证方法（get）与路径
        expect(getMock).toHaveBeenCalledTimes(1)
        expect(getMock).toHaveBeenCalledWith('/api/v1/quality/posterior/1/result')
        expect(postMock).not.toHaveBeenCalled()
    })

    it('成功时返回 PosteriorStats 统计数据', async () => {
        const stats = makePosteriorStats({ project_id: 7, scored_cases: 5, unscored_cases: 0 })
        getMock.mockResolvedValueOnce({ code: 0, message: 'success', data: stats })

        const res = await getPosteriorResult(7)

        expect(res.data).toEqual(stats)
        expect(res.data.scored_cases).toBe(5)
        expect(res.data.distribution.A_90_100).toBe(3)
    })

    it('尚未评分时 avg_posterior_score 为 null 仍正常返回', async () => {
        // 边界场景：项目无评分数据，统计字段为 null
        getMock.mockResolvedValueOnce({
            code: 0,
            message: 'success',
            data: makePosteriorStats({
                avg_posterior_score: null,
                max_posterior_score: null,
                min_posterior_score: null,
                scored_cases: 0,
                unscored_cases: 12,
            }),
        })

        const res = await getPosteriorResult(1)

        expect(res.data.avg_posterior_score).toBeNull()
        expect(res.data.scored_cases).toBe(0)
    })

    it('请求失败时抛出异常', async () => {
        getMock.mockRejectedValueOnce(new Error('网络错误'))

        await expect(getPosteriorResult(1)).rejects.toThrow('网络错误')
        expect(getMock).toHaveBeenCalledWith('/api/v1/quality/posterior/1/result')
    })
})
