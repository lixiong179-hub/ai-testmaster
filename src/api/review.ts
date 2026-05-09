import request from '@/utils/request'

export interface ReviewDecision {
  id: number
  target_kind: string
  target_id: number
  target_version?: number
  ai_verdict?: string
  ai_confidence?: number
  ai_reason?: string
  modification_hint?: string
  deprecate_reason?: string
  human_verdict?: string
  human_user_id?: number
  human_reason?: string
  final_verdict?: string
  conflict_marker: boolean
  accepted_low_confidence: boolean
  decided_at?: string
}

export interface ReviewMeta {
  status: string | null
  finalized_at: string | null
  finalized_by: number | null
  undo_window_expires_at: string | null
}

export interface DecisionListResponse {
  code: number
  message: string
  data: {
    decisions: ReviewDecision[]
    total: number
    review: ReviewMeta | null
  }
}

export interface DecideRequest {
  human_verdict: string
  human_reason?: string
}

export interface BatchDecideItem {
  decision_id: number
  human_verdict: string
  human_reason?: string
}

export interface BatchDecideRequest {
  decisions: BatchDecideItem[]
}

export interface FinalizeResponse {
  code: number
  message: string
  data: {
    review_id: number
    status: string
    finalized_at: string | null
    finalized_by: number | null
  }
}

export const reviewApi = {
  getDecisions: async (
    reviewId: number,
    params?: {
      verdict?: string
      target_kind?: string
      sort_by?: string
      order?: string
    }
  ): Promise<DecisionListResponse> => {
    return request.get(`/api/v1/review/${reviewId}/decisions`, { params })
  },

  decideSingle: async (
    reviewId: number,
    decisionId: number,
    data: DecideRequest
  ): Promise<{ code: number; message: string; data: ReviewDecision }> => {
    return request.post(`/api/v1/review/${reviewId}/decisions/${decisionId}/decide`, data)
  },

  decideBatch: async (
    reviewId: number,
    data: BatchDecideRequest
  ): Promise<{
    code: number
    message: string
    data: { decisions: ReviewDecision[]; total: number }
  }> => {
    return request.post(`/api/v1/review/${reviewId}/decisions/batch-decide`, data)
  },

  finalizeReview: async (reviewId: number): Promise<FinalizeResponse> => {
    return request.post(`/api/v1/review/${reviewId}/finalize`)
  },

  undoDecision: async (
    reviewId: number,
    decisionId: number
  ): Promise<{ code: number; message: string; data: ReviewDecision }> => {
    return request.post(`/api/v1/review/${reviewId}/undo-decision/${decisionId}`)
  },

  rollbackDecision: async (
    reviewId: number,
    decisionId: number
  ): Promise<{ code: number; message: string; data: ReviewDecision }> => {
    return request.post(`/api/v1/review/${reviewId}/decisions/${decisionId}/rollback`)
  },

  undoFinalize: async (reviewId: number): Promise<FinalizeResponse> => {
    return request.post(`/api/v1/review/${reviewId}/undo-finalize`)
  },
}

export default reviewApi
