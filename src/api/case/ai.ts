import request from '@/utils/request'
import type { ApiResponse } from '@/utils/request'
import type { TestCase } from '@/types/testCase'
import type { TestCaseAIGenerate } from '@/types/testCase'
import type {
  TestCaseAIEnhancedRequest,
  AIEnhancedGenerateResponse,
  AIEnhancedGenerateResult,
  LineageResponse,
} from './types'
import { extractResponseData } from './types'

export const aiApi = {
  aiGenerateCase: async (data: TestCaseAIGenerate): Promise<TestCase> => {
    const response = await request.post('/api/v1/testCase/ai-generate', data)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  aiGenerateCaseEnhanced: async (
    data: TestCaseAIEnhancedRequest
  ): Promise<AIEnhancedGenerateResult> => {
    const response = await request.post('/api/v1/testCase/ai-enhanced-generate', data)
    const dataResult = extractResponseData<AIEnhancedGenerateResponse[] | AIEnhancedGenerateResult>(
      response as unknown as
        | ApiResponse<AIEnhancedGenerateResponse[] | AIEnhancedGenerateResult>
        | AIEnhancedGenerateResponse[]
        | AIEnhancedGenerateResult
    )
    return Array.isArray(dataResult) ? { cases: dataResult } : dataResult
  },

  getLineage: async (caseId: number): Promise<LineageResponse> => {
    const response = await request.get(`/api/v1/testCase/${caseId}/lineage`)
    return extractResponseData<LineageResponse>(
      response as unknown as ApiResponse<LineageResponse> | LineageResponse
    )
  },

  generateContext: async (data: Record<string, unknown>) => {
    return request.post('/api/v1/testCase/generate-context', data)
  },

  previewGraphPrompt: async (data: Record<string, unknown>) => {
    return request.post('/api/v1/testCase/preview-graph-prompt', data)
  },
}
