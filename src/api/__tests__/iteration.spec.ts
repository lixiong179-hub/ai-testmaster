import { describe, it, expect, beforeEach, vi } from 'vitest'

// 使用 vi.hoisted 确保 mock 对象在 vi.mock 工厂执行前已初始化
const { mockRequest } = vi.hoisted(() => ({
    mockRequest: {
        get: vi.fn(),
        post: vi.fn(),
        put: vi.fn(),
        delete: vi.fn(),
    },
}))

vi.mock('@/utils/request', () => ({
    default: mockRequest,
}))

import { finalizeIteration, runPipeline } from '@/api/iteration'
import type { Iteration, PipelineRunResponse } from '@/api/iteration'

function makeIteration(overrides: Partial<Iteration> = {}): Iteration {
    return {
        id: 1,
        project_id: 10,
        name: '迭代1',
        version: 'v1.0',
        status: 'finalized',
        create_time: '2026-01-01T00:00:00',
        update_time: '2026-01-01T00:00:00',
        ...overrides,
    }
}

function makeRunResponse(overrides: Partial<PipelineRunResponse> = {}): PipelineRunResponse {
    return {
        run_id: 100,
        iteration_id: 1,
        status: 'running',
        scenario: 1,
        ...overrides,
    }
}

describe('finalizeIteration', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('成功: 调用 POST /api/v1/iteration/{id}/finalize 并返回数据', async () => {
        const mockIteration = makeIteration({ id: 1, status: 'finalized' })
        mockRequest.post.mockResolvedValueOnce({
            code: 0,
            msg: '定稿成功',
            message: '定稿成功',
            data: mockIteration,
        })

        const res = await finalizeIteration(1)

        expect(mockRequest.post).toHaveBeenCalledTimes(1)
        expect(mockRequest.post).toHaveBeenCalledWith('/api/v1/iteration/1/finalize')
        expect(res.code).toBe(0)
        expect(res.data).toEqual(mockIteration)
        expect(res.data.status).toBe('finalized')
    })

    it('成功: 不同 iterationId 拼接到路径', async () => {
        const mockIteration = makeIteration({ id: 42, status: 'finalized' })
        mockRequest.post.mockResolvedValueOnce({
            code: 0,
            msg: '定稿成功',
            message: '定稿成功',
            data: mockIteration,
        })

        const res = await finalizeIteration(42)

        expect(mockRequest.post).toHaveBeenCalledWith('/api/v1/iteration/42/finalize')
        expect(res.code).toBe(0)
        expect(res.data.id).toBe(42)
    })

    it('失败: Error 异常被捕获并返回标准错误格式', async () => {
        mockRequest.post.mockRejectedValueOnce(new Error('迭代状态非法，不可定稿'))

        const res = await finalizeIteration(999)

        expect(mockRequest.post).toHaveBeenCalledWith('/api/v1/iteration/999/finalize')
        expect(res.code).toBe(-1)
        expect(res.message).toBe('迭代状态非法，不可定稿')
        expect(res.msg).toBe('迭代状态非法，不可定稿')
    })

    it('失败: 非Error异常使用默认提示文案', async () => {
        mockRequest.post.mockRejectedValueOnce('网络异常字符串')

        const res = await finalizeIteration(1)

        expect(res.code).toBe(-1)
        expect(res.message).toBe('定稿迭代失败')
    })
})

describe('runPipeline', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('成功: 默认 scenario=1 调用 POST /api/v1/iteration/{id}/pipeline/run', async () => {
        const mockData = makeRunResponse({ run_id: 100, scenario: 1 })
        mockRequest.post.mockResolvedValueOnce({
            code: 0,
            msg: 'success',
            message: 'success',
            data: mockData,
        })

        const res = await runPipeline(1)

        expect(mockRequest.post).toHaveBeenCalledTimes(1)
        expect(mockRequest.post).toHaveBeenCalledWith(
            '/api/v1/iteration/1/pipeline/run',
            { scenario: 1 }
        )
        expect(res.code).toBe(0)
        expect(res.data.run_id).toBe(100)
        expect(res.data.scenario).toBe(1)
    })

    it('成功: 自定义 scenario=3 (回归) 透传到请求体', async () => {
        const mockData = makeRunResponse({ run_id: 101, scenario: 3 })
        mockRequest.post.mockResolvedValueOnce({
            code: 0,
            msg: 'success',
            message: 'success',
            data: mockData,
        })

        const res = await runPipeline(1, 3)

        expect(mockRequest.post).toHaveBeenCalledWith(
            '/api/v1/iteration/1/pipeline/run',
            { scenario: 3 }
        )
        expect(res.data.scenario).toBe(3)
    })

    it('成功: scenario=4 (UI回归) 路径与参数正确', async () => {
        const mockData = makeRunResponse({ run_id: 102, scenario: 4 })
        mockRequest.post.mockResolvedValueOnce({
            code: 0,
            msg: 'success',
            message: 'success',
            data: mockData,
        })

        const res = await runPipeline(7, 4)

        expect(mockRequest.post).toHaveBeenCalledWith(
            '/api/v1/iteration/7/pipeline/run',
            { scenario: 4 }
        )
        expect(res.data.run_id).toBe(102)
    })

    it('失败: Error 异常被捕获并返回标准错误格式', async () => {
        mockRequest.post.mockRejectedValueOnce(new Error('Pipeline 启动失败'))

        const res = await runPipeline(1, 2)

        expect(mockRequest.post).toHaveBeenCalledWith(
            '/api/v1/iteration/1/pipeline/run',
            { scenario: 2 }
        )
        expect(res.code).toBe(-1)
        expect(res.message).toBe('Pipeline 启动失败')
    })

    it('失败: 非Error异常使用默认提示文案', async () => {
        mockRequest.post.mockRejectedValueOnce(null)

        const res = await runPipeline(1)

        expect(res.code).toBe(-1)
        expect(res.message).toBe('启动 Pipeline 失败')
    })
})
