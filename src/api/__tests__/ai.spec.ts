import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// Task13: 智能生成底层统一为 Pipeline 集成测试。
// 验证 generateCasesViaPipeline 调用 Pipeline API 而非原 test-case/ai-generate，
// 覆盖正常生成、缓存命中、失败、中断、@deprecated 回退等场景。

interface ApiResponseData<T> {
    code: number
    message: string
    data: T
}

// 使用 vi.hoisted 确保 mock 在 vi.mock 工厂执行前已初始化
const { mockRequest, mockPipelineApi } = vi.hoisted(() => ({
    mockRequest: {
        post: vi.fn(),
        get: vi.fn(),
    },
    mockPipelineApi: {
        runPipeline: vi.fn(),
        getPipelineRun: vi.fn(),
        getArtifactDetail: vi.fn(),
    },
}))

vi.mock('@/utils/request', () => ({
    default: mockRequest,
}))

vi.mock('@/api/pipeline', () => ({
    pipelineApi: mockPipelineApi,
}))

import { aiApi, generateCasesViaPipeline } from '@/api/case/ai'
import type { PipelineRun } from '@/api/pipeline'

/** 构造 PipelineRun mock 数据 */
function makePipelineRun(overrides: Partial<PipelineRun> = {}): PipelineRun {
    return {
        id: 100,
        iteration_id: 1,
        input_hash: 'hash-abc',
        pipeline_version: '1.0',
        status: 'completed',
        started_at: '2026-07-30T00:00:00',
        finished_at: '2026-07-30T00:01:00',
        error: null,
        pause_payload: null,
        steps: [
            {
                id: 1,
                step_name: 'signal_gatherer',
                status: 'done',
                started_at: null,
                finished_at: null,
                error: null,
                retried_count: 0,
                degraded: false,
            },
            {
                id: 2,
                step_name: 'case_generation',
                status: 'done',
                started_at: null,
                finished_at: null,
                error: null,
                retried_count: 0,
                degraded: false,
            },
        ],
        artifacts: [
            {
                id: 200,
                kind: 'generated_cases',
                confidence: 0.9,
                schema_version: '1.0',
                created_at: '2026-07-30T00:01:00',
            },
        ],
        ...overrides,
    }
}

/** 构造 generated_cases 产物详情 mock */
function makeGeneratedCasesArtifactPayload(cases: Record<string, unknown>[]) {
    return {
        data: {
            artifact_id: 200,
            run_id: 100,
            kind: 'generated_cases',
            schema_version: '1.0',
            payload: {
                generated_cases: cases,
                total: cases.length,
                success_count: cases.length,
                failed_count: 0,
                has_ui: true,
            },
            confidence: 0.9,
            provenance: {},
            content_hash: 'content-abc',
            created_at: '2026-07-30T00:01:00',
            truncated: false,
            truncated_reason: null,
        },
    }
}

/** 构造单条生成用例 mock */
function makeRawCase(overrides: Record<string, unknown> = {}): Record<string, unknown> {
    return {
        title: '登录成功用例',
        module: '登录模块',
        precondition: '已打开登录页',
        steps: [{ step: 1, action: '输入账号', expected_result: '显示输入' }],
        expected_result: '登录成功',
        priority: 1,
        case_type: 'ui_automation',
        test_point_id: 42,
        ...overrides,
    }
}

function makeIterationResponse(id: number = 1): ApiResponseData<{ id: number }> {
    return { code: 0, message: '创建成功', data: { id } }
}

beforeEach(() => {
    vi.clearAllMocks()
})

afterEach(() => {
    vi.useRealTimers()
})

describe('generateCasesViaPipeline - Task13 底层统一为 Pipeline', () => {
    it('成功: 调用 Pipeline API 而非 test-case/ai-generate', async () => {
        const iterationId = 7
        const runId = 88
        mockRequest.post.mockImplementation((url: string) => {
            if (url === '/api/v1/iteration/') {
                return Promise.resolve(makeIterationResponse(iterationId))
            }
            if (url.startsWith(`/api/v1/iteration/${iterationId}/inputs`)) {
                return Promise.resolve({ code: 0, message: 'ok', data: {} })
            }
            return Promise.reject(new Error(`unexpected POST ${url}`))
        })
        mockPipelineApi.runPipeline.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: { run_id: runId, iteration_id: iterationId, status: 'running', scenario: 1 },
        })
        mockPipelineApi.getPipelineRun.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: makePipelineRun({ id: runId, iteration_id: iterationId }),
        })
        mockPipelineApi.getArtifactDetail.mockResolvedValueOnce(
            makeGeneratedCasesArtifactPayload([makeRawCase()])
        )

        const result = await generateCasesViaPipeline({
            projectId: 10,
            requirementFileIds: [101],
            testPointIds: [42],
            uiScreenIds: [201],
        })

        // 验证创建了迭代
        expect(mockRequest.post).toHaveBeenCalledWith(
            '/api/v1/iteration/',
            expect.objectContaining({ project_id: 10 })
        )
        // 验证添加了 PRD/testpoint/prototype 三类输入
        const inputCalls = mockRequest.post.mock.calls.filter((c) =>
            String(c[0]).includes('/inputs')
        )
        expect(inputCalls).toHaveLength(3)
        // 验证调用 Pipeline run 而非 test-case/ai-generate
        expect(mockPipelineApi.runPipeline).toHaveBeenCalledWith(iterationId, { scenario: 1 })
        const aiGenerateCalls = mockRequest.post.mock.calls.filter((c) =>
            String(c[0]).includes('/ai-generate')
        )
        expect(aiGenerateCalls).toHaveLength(0)
        // 验证返回用例
        expect(result.cases).toHaveLength(1)
        expect(result.cases[0].title).toBe('登录成功用例')
        expect(result.cases[0].test_point_id).toBe(42)
        expect(result.runId).toBe(runId)
        expect(result.iterationId).toBe(iterationId)
    })

    it('成功: 调用方显式传 scenario=2 时透传给 Pipeline', async () => {
        // ai.ts 不自动推断场景（由 store 层 selectPipelineScenario 决定），仅透传 scenario 参数
        mockRequest.post.mockResolvedValue(makeIterationResponse(3))
        mockPipelineApi.runPipeline.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: { run_id: 5, iteration_id: 3, status: 'running', scenario: 2 },
        })
        mockPipelineApi.getPipelineRun.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: makePipelineRun({ id: 5, iteration_id: 3 }),
        })
        mockPipelineApi.getArtifactDetail.mockResolvedValueOnce(
            makeGeneratedCasesArtifactPayload([makeRawCase()])
        )

        await generateCasesViaPipeline({
            projectId: 10,
            requirementFileIds: [101],
            testPointIds: [42],
            uiScreenIds: [],
            scenario: 2,
        })

        expect(mockPipelineApi.runPipeline).toHaveBeenCalledWith(3, { scenario: 2 })
        // 无 UI 时不应添加 prototype 输入
        const prototypeCalls = mockRequest.post.mock.calls.filter(
            (c) =>
                String(c[0]).includes('/inputs') &&
                (c[1] as Record<string, unknown>).kind === 'prototype'
        )
        expect(prototypeCalls).toHaveLength(0)
    })

    it('成功: 未传 scenario 时使用默认值 1', async () => {
        mockRequest.post.mockResolvedValue(makeIterationResponse(3))
        mockPipelineApi.runPipeline.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: { run_id: 5, iteration_id: 3, status: 'running', scenario: 1 },
        })
        mockPipelineApi.getPipelineRun.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: makePipelineRun({ id: 5, iteration_id: 3 }),
        })
        mockPipelineApi.getArtifactDetail.mockResolvedValueOnce(
            makeGeneratedCasesArtifactPayload([makeRawCase()])
        )

        await generateCasesViaPipeline({
            projectId: 10,
            requirementFileIds: [101],
            testPointIds: [42],
            uiScreenIds: [],
        })

        expect(mockPipelineApi.runPipeline).toHaveBeenCalledWith(3, { scenario: 1 })
    })

    it('缓存命中: Pipeline 秒级完成时 cached=true', async () => {
        mockRequest.post.mockResolvedValue(makeIterationResponse(1))
        mockPipelineApi.runPipeline.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: { run_id: 100, iteration_id: 1, status: 'completed', scenario: 1 },
        })
        // 首次轮询即返回 completed（缓存命中，秒级返回）
        mockPipelineApi.getPipelineRun.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: makePipelineRun({ id: 100, iteration_id: 1, status: 'completed' }),
        })
        mockPipelineApi.getArtifactDetail.mockResolvedValueOnce(
            makeGeneratedCasesArtifactPayload([makeRawCase()])
        )

        const result = await generateCasesViaPipeline({
            projectId: 10,
            requirementFileIds: [101],
            testPointIds: [42],
            uiScreenIds: [201],
        })

        expect(result.cached).toBe(true)
        // 缓存命中时只轮询一次（fetchGeneratedCases 复用 finalRun，不再二次调用 getPipelineRun）
        expect(mockPipelineApi.getPipelineRun).toHaveBeenCalledTimes(1)
    })

    it('失败: Pipeline 状态为 failed 时抛出错误', async () => {
        mockRequest.post.mockResolvedValue(makeIterationResponse(1))
        mockPipelineApi.runPipeline.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: { run_id: 100, iteration_id: 1, status: 'running', scenario: 1 },
        })
        mockPipelineApi.getPipelineRun.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: makePipelineRun({
                id: 100,
                iteration_id: 1,
                status: 'failed',
                error: '场景 1 需要有效 PRD 输入',
            }),
        })

        await expect(
            generateCasesViaPipeline({
                projectId: 10,
                requirementFileIds: [],
                testPointIds: [42],
                uiScreenIds: [],
            })
        ).rejects.toThrow('场景 1 需要有效 PRD 输入')
    })

    it('失败: Pipeline 启动未返回 run_id 时抛出错误', async () => {
        mockRequest.post.mockResolvedValue(makeIterationResponse(1))
        mockPipelineApi.runPipeline.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: { run_id: 0, iteration_id: 1, status: 'running', scenario: 1 },
        })

        await expect(
            generateCasesViaPipeline({
                projectId: 10,
                requirementFileIds: [101],
                testPointIds: [42],
                uiScreenIds: [],
            })
        ).rejects.toThrow('Pipeline 启动失败')
    })

    it('中断: AbortSignal 已取消时抛出 AbortError', async () => {
        const controller = new AbortController()
        controller.abort()

        await expect(
            generateCasesViaPipeline({
                projectId: 10,
                requirementFileIds: [101],
                testPointIds: [42],
                uiScreenIds: [],
                signal: controller.signal,
            })
        ).rejects.toThrow()
    })

    it('中断: 轮询期间取消抛出 AbortError', async () => {
        mockRequest.post.mockResolvedValue(makeIterationResponse(1))
        mockPipelineApi.runPipeline.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: { run_id: 100, iteration_id: 1, status: 'running', scenario: 1 },
        })
        const controller = new AbortController()
        // 首次轮询返回 running，触发 delay，此时取消
        mockPipelineApi.getPipelineRun.mockImplementationOnce(() => {
            controller.abort()
            return Promise.resolve({
                code: 0,
                message: 'ok',
                data: makePipelineRun({ id: 100, iteration_id: 1, status: 'running' }),
            })
        })

        await expect(
            generateCasesViaPipeline({
                projectId: 10,
                requirementFileIds: [101],
                testPointIds: [42],
                uiScreenIds: [],
                signal: controller.signal,
            })
        ).rejects.toThrow()
    })

    it('进度回调: 轮询时透传 stepName 与 percent', async () => {
        mockRequest.post.mockResolvedValue(makeIterationResponse(1))
        mockPipelineApi.runPipeline.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: { run_id: 100, iteration_id: 1, status: 'running', scenario: 1 },
        })
        mockPipelineApi.getPipelineRun.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: makePipelineRun({
                id: 100,
                iteration_id: 1,
                status: 'running',
                steps: [
                    {
                        id: 1,
                        step_name: 'case_generation',
                        status: 'running',
                        started_at: null,
                        finished_at: null,
                        error: null,
                        retried_count: 0,
                        degraded: false,
                    },
                ],
            }),
        })
        mockPipelineApi.getPipelineRun.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: makePipelineRun({ id: 100, iteration_id: 1, status: 'completed' }),
        })
        mockPipelineApi.getArtifactDetail.mockResolvedValueOnce(
            makeGeneratedCasesArtifactPayload([makeRawCase()])
        )

        const progressCalls: { stepName?: string; percent: number | null }[] = []
        await generateCasesViaPipeline({
            projectId: 10,
            requirementFileIds: [101],
            testPointIds: [42],
            uiScreenIds: [201],
            onProgress: (p) => progressCalls.push({ stepName: p.stepName, percent: p.percent }),
        })

        // 至少有一次进度回调包含 stepName=case_generation
        expect(progressCalls.some((p) => p.stepName === 'case_generation')).toBe(true)
    })
})

describe('aiApi.aiGenerateCaseEnhanced - @deprecated 回退路径', () => {
    it('仍调用原 test-case/ai-enhanced-generate 端点', async () => {
        const mockCase = {
            case_id: 1,
            case_no: 'C001',
            title: '旧路径用例',
            steps: [],
            test_data: {},
            message: 'ok',
        }
        mockRequest.post.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: [mockCase],
        })

        const result = await aiApi.aiGenerateCaseEnhanced({
            project_id: 10,
            description: '测试',
        })

        expect(mockRequest.post).toHaveBeenCalledWith(
            '/api/v1/test-case/ai-enhanced-generate',
            expect.objectContaining({ project_id: 10 })
        )
        // 未调用 Pipeline
        expect(mockPipelineApi.runPipeline).not.toHaveBeenCalled()
        expect(result.cases).toHaveLength(1)
        expect(result.cases[0].title).toBe('旧路径用例')
    })
})

describe('aiApi.aiGenerateCase - @deprecated 回退路径', () => {
    it('仍调用原 test-case/ai-generate 端点', async () => {
        mockRequest.post.mockResolvedValueOnce({
            code: 0,
            message: 'ok',
            data: { id: 1, title: '基础生成用例' },
        })

        await aiApi.aiGenerateCase({
            project_id: 10,
            description: '测试',
        } as never)

        expect(mockRequest.post).toHaveBeenCalledWith(
            '/api/v1/test-case/ai-generate',
            expect.objectContaining({ project_id: 10 })
        )
        expect(mockPipelineApi.runPipeline).not.toHaveBeenCalled()
    })
})
