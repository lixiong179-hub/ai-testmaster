import request from '@/utils/request'
import type { ApiResponse } from '@/utils/request'
import type { TestCase } from '@/types/testCase'
import type { TestCaseAIGenerate } from '@/types/testCase'
import type {
  TestCaseAIEnhancedRequest,
  AIEnhancedGenerateResponse,
  TestCaseGenerateRequest,
  LineageResponse,
} from './types'
import { extractResponseData } from './types'

function createStreamGenerator(
  stream: ReadableStream
): AsyncGenerator<{ progress: number; message?: string }> {
  const reader = stream.getReader()
  return (async function* () {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = new TextDecoder('utf-8').decode(value)
      const lines = chunk.split('\n')
      for (const line of lines) {
        if (line.trim()) {
          try {
            const progress: { progress: number; message?: string } = JSON.parse(line)
            yield progress
          } catch (e: unknown) {
            console.error('解析进度数据失败:', e instanceof Error ? e.message : String(e))
          }
        }
      }
    }
  })()
}

export const aiApi = {
  aiGenerateCase: async (data: TestCaseAIGenerate): Promise<TestCase> => {
    const response = await request.post('/api/v1/testCase/ai-generate', data)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  aiGenerateCaseEnhanced: async (
    data: TestCaseAIEnhancedRequest
  ): Promise<AIEnhancedGenerateResponse[]> => {
    const response = await request.post('/api/v1/testCase/ai-enhanced-generate', data)
    return extractResponseData<AIEnhancedGenerateResponse[]>(
      response as unknown as ApiResponse<AIEnhancedGenerateResponse[]> | AIEnhancedGenerateResponse[]
    )
  },

  generate: async (
    data: TestCaseGenerateRequest
  ): Promise<AsyncGenerator<{ progress: number; message?: string }>> => {
    const response = await request.post('/api/v1/testCase/batch-generate/stream', data, {
      responseType: 'stream',
    })
    return new Promise((resolve) => {
      resolve(createStreamGenerator(response.data as ReadableStream))
    })
  },

  /**
   * AI增强生成（流式）
   * 后端：POST /api/v1/testCase/ai-enhanced-generate/stream
   */
  generateEnhancedStream: async (
    data: TestCaseAIEnhancedRequest
  ): Promise<AsyncGenerator<{ progress: number; message?: string }>> => {
    const response = await request.post('/api/v1/testCase/ai-enhanced-generate/stream', data, {
      responseType: 'stream',
    })
    return new Promise((resolve) => {
      resolve(createStreamGenerator(response.data as ReadableStream))
    })
  },

  getLineage: async (caseId: number): Promise<LineageResponse> => {
    const response = await request.get(`/api/v1/testCase/${caseId}/lineage`)
    return extractResponseData<LineageResponse>(
      response as unknown as ApiResponse<LineageResponse> | LineageResponse
    )
  },
}
