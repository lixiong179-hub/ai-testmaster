import request from '@/utils/request'
import type { ApiResponse } from '@/utils/request'
import { pipelineApi } from '@/api/pipeline'
import type { ArtifactDetail, PipelineRun, PipelineStep } from '@/api/pipeline'
import type { TestCase } from '@/types/testCase'
import type { TestCaseAIGenerate } from '@/types/testCase'
import type {
  TestCaseAIEnhancedRequest,
  AIEnhancedGenerateResponse,
  AIEnhancedGenerateResult,
  LineageResponse,
} from './types'
import { extractResponseData } from './types'

// ========== 智能生成：底层统一为 Pipeline（Task13） ==========

/** Pipeline 默认场景编号（1=冒烟） */
const DEFAULT_PIPELINE_SCENARIO = 1
/** 轮询间隔（毫秒） */
const POLL_INTERVAL_MS = 800
/** 最大轮询次数（防止无限等待） */
const MAX_POLL_ATTEMPTS = 600

/** Pipeline generated_cases 产物中的单条用例（原始结构，字段随 AI 输出） */
export interface GeneratedCaseDraft {
  title?: string
  module?: string
  precondition?: string
  steps?: Array<Record<string, unknown>>
  expected_result?: string
  priority?: number
  case_type?: string
  test_point_id?: number
  [key: string]: unknown
}

/** 生成过程进度（供调用方展示步骤名与百分比） */
export interface PipelineGenerationProgress {
  stepName?: string
  percent: number | null
  status?: string
}

/** generateCasesViaPipeline 入参 */
export interface GenerateCasesViaPipelineOptions {
  projectId: number
  requirementFileIds: number[]
  testPointIds: number[]
  uiScreenIds: number[]
  /** Pipeline 场景编号；场景推断由 store 层负责，本层仅透传（默认 1） */
  scenario?: number
  signal?: AbortSignal
  onProgress?: (progress: PipelineGenerationProgress) => void
}

/** generateCasesViaPipeline 返回值 */
export interface GenerateCasesViaPipelineResult {
  cases: GeneratedCaseDraft[]
  runId: number
  iterationId: number
  /** 是否缓存命中（首次轮询即为 completed，无需等待） */
  cached: boolean
}

function createAbortError(): Error {
  const error = new Error('生成已取消')
  error.name = 'AbortError'
  return error
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw createAbortError()
  }
}

/** 可被 AbortSignal 打断的延时 */
function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(createAbortError())
      return
    }
    const cleanup = () => {
      clearTimeout(timer)
      signal?.removeEventListener('abort', onAbort)
    }
    const onAbort = () => {
      cleanup()
      reject(createAbortError())
    }
    const timer = setTimeout(() => {
      cleanup()
      resolve()
    }, ms)
    signal?.addEventListener('abort', onAbort)
  })
}

/** 兼容 `{code,data}` 与 `{data}` 两种响应形态的解包 */
function unwrap<T>(response: unknown): T | null {
  if (response && typeof response === 'object' && 'data' in (response as Record<string, unknown>)) {
    return ((response as { data: T }).data ?? null) as T | null
  }
  return (response as T) ?? null
}

/** 输入内容哈希（FNV-1a 32 位，后端用于幂等校验，长度 ≤ 64） */
function hashPayload(value: unknown): string {
  const text = JSON.stringify(value)
  let hash = 0x811c9dc5
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return `h${hash.toString(16).padStart(8, '0')}`
}

/** 汇总运行进度并回调 */
function emitProgress(
  run: PipelineRun | null | undefined,
  onProgress?: (progress: PipelineGenerationProgress) => void
): void {
  if (!onProgress) {
    return
  }
  const steps: PipelineStep[] = run?.steps ?? []
  const running = steps.find((step) => step.status === 'running')
  const finished = steps.filter((step) => step.status === 'done' || step.status === 'skipped').length
  onProgress({
    stepName: running?.step_name,
    percent: steps.length > 0 ? Math.round((finished / steps.length) * 100) : null,
    status: run?.status,
  })
}

/** 从运行结果的 generated_cases 产物中取出用例 */
async function fetchGeneratedCases(
  run: PipelineRun | null,
  runId: number
): Promise<GeneratedCaseDraft[]> {
  const artifact = (run?.artifacts ?? []).find((item) => item.kind === 'generated_cases')
  if (!artifact) {
    return []
  }
  const detailResponse = await pipelineApi.getArtifactDetail(runId, artifact.id)
  const detail = unwrap<ArtifactDetail>(detailResponse)
  const payload = (detail?.payload ?? null) as Record<string, unknown> | null
  const rawCases = payload?.generated_cases
  return Array.isArray(rawCases) ? (rawCases as GeneratedCaseDraft[]) : []
}

/**
 * 通过 Pipeline 生成测试用例（Task13：替代原 `test-case/ai-generate` 直连）
 *
 * 流程：创建迭代 → 写入 PRD/测试点/UI 原型输入 → 启动 Pipeline（指定场景）
 *      → 轮询至终态 → 读取 generated_cases 产物
 *
 * 与旧实现的差异：本项目不再直接调用大模型生成端点，生成逻辑统一收敛到 Pipeline，
 * 从而复用缓存、场景编排与产物留痕能力。场景编号由调用方（store）决定并透传。
 *
 * @throws Pipeline 启动失败、执行失败（failed/cancelled）或超时；取消时抛出 name=AbortError
 */
export async function generateCasesViaPipeline(
  options: GenerateCasesViaPipelineOptions
): Promise<GenerateCasesViaPipelineResult> {
  const {
    projectId,
    requirementFileIds,
    testPointIds,
    uiScreenIds,
    scenario = DEFAULT_PIPELINE_SCENARIO,
    signal,
    onProgress,
  } = options

  throwIfAborted(signal)

  // 1. 创建迭代（Pipeline 以迭代为执行单元）
  const iterationResponse = await request.post('/api/v1/iteration/', {
    project_id: projectId,
    name: `智能生成-${Date.now()}`,
  })
  const iterationId = unwrap<{ id?: number }>(iterationResponse)?.id
  if (!iterationId) {
    throw new Error('创建迭代失败')
  }

  // 2. 写入三类输入（PRD / 测试点 / UI 原型），hash 用于后端幂等
  const inputs: Array<{ kind: string; file_id?: number; payload: Record<string, unknown> }> = [
    {
      kind: 'prd',
      file_id: requirementFileIds[0],
      payload: { file_ids: requirementFileIds },
    },
    {
      kind: 'testpoint',
      payload: { test_point_ids: testPointIds },
    },
  ]
  if (uiScreenIds.length > 0) {
    inputs.push({
      kind: 'prototype',
      file_id: uiScreenIds[0],
      payload: { file_ids: uiScreenIds },
    })
  }
  for (const input of inputs) {
    throwIfAborted(signal)
    await request.post(`/api/v1/iteration/${iterationId}/inputs`, {
      ...input,
      hash: hashPayload(input),
    })
  }

  // 3. 启动 Pipeline
  throwIfAborted(signal)
  const started = unwrap<{ run_id?: number; pipeline_run_id?: number }>(
    await pipelineApi.runPipeline(iterationId, { scenario })
  )
  const runId = started?.run_id || started?.pipeline_run_id || 0
  if (!runId) {
    throw new Error('Pipeline 启动失败')
  }

  // 4. 轮询至终态；首次即为 completed 说明命中缓存
  let run = unwrap<PipelineRun>(await pipelineApi.getPipelineRun(runId))
  emitProgress(run, onProgress)
  const cached = run?.status === 'completed'

  let attempts = 0
  while (run && run.status !== 'completed' && run.status !== 'failed' && run.status !== 'cancelled') {
    if (attempts >= MAX_POLL_ATTEMPTS) {
      throw new Error('Pipeline 执行超时')
    }
    attempts += 1
    await wait(POLL_INTERVAL_MS, signal)
    throwIfAborted(signal)
    run = unwrap<PipelineRun>(await pipelineApi.getPipelineRun(runId))
    emitProgress(run, onProgress)
  }

  if (run?.status === 'failed') {
    throw new Error(run.error || 'Pipeline 执行失败')
  }
  if (run?.status === 'cancelled') {
    throw new Error('Pipeline 已取消')
  }

  // 5. 读取生成用例产物
  const cases = await fetchGeneratedCases(run, runId)
  return { cases, runId, iterationId, cached }
}

export const aiApi = {
  aiGenerateCase: async (data: TestCaseAIGenerate): Promise<TestCase> => {
    const response = await request.post('/api/v1/test-case/ai-generate', data)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  aiGenerateCaseEnhanced: async (
    data: TestCaseAIEnhancedRequest
  ): Promise<AIEnhancedGenerateResult> => {
    const response = await request.post('/api/v1/test-case/ai-enhanced-generate', data)
    const dataResult = extractResponseData<AIEnhancedGenerateResponse[] | AIEnhancedGenerateResult>(
      response as unknown as
        | ApiResponse<AIEnhancedGenerateResponse[] | AIEnhancedGenerateResult>
        | AIEnhancedGenerateResponse[]
        | AIEnhancedGenerateResult
    )
    return Array.isArray(dataResult) ? { cases: dataResult } : dataResult
  },

  getLineage: async (caseId: number): Promise<LineageResponse> => {
    const response = await request.get(`/api/v1/test-case/${caseId}/lineage`)
    return extractResponseData<LineageResponse>(
      response as unknown as ApiResponse<LineageResponse> | LineageResponse
    )
  },

  generateContext: async (data: Record<string, unknown>) => {
    return request.post('/api/v1/test-case/generate-context', data)
  },

  previewGraphPrompt: async (data: Record<string, unknown>) => {
    return request.post('/api/v1/test-case/preview-graph-prompt', data)
  },
}
