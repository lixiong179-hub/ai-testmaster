import request from '@/utils/request'

export type PipelineRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'waiting_for_user' | 'cancelled'
export type PipelineStepStatus = 'pending' | 'running' | 'done' | 'failed' | 'skipped' | 'degraded'

export interface PipelineStep {
  id: number
  step_name: string
  status: PipelineStepStatus
  started_at: string | null
  finished_at: string | null
  error: string | null
  retried_count: number
  degraded: boolean
}

export interface PipelineArtifact {
  id: number
  kind: string
  confidence: number | null
  schema_version: string | null
  created_at: string | null
}

export interface PipelineRun {
  id: number
  iteration_id: number
  input_hash: string
  pipeline_version: string
  status: PipelineRunStatus
  started_at: string | null
  finished_at: string | null
  error: string | null
  pause_payload: Record<string, unknown> | null
  steps: PipelineStep[]
  artifacts: PipelineArtifact[]
}

export interface PipelineRunRequest {
  scenario: number
  ai_model?: string
  dry_run?: boolean
}

export interface PipelineResumeRequest {
  confirmation_payload?: Record<string, unknown>
}

export interface PipelineRunResponse {
  run_id: number
  iteration_id: number
  status: PipelineRunStatus
  scenario: number
}

export interface PipelineResumeResponse {
  run_id: number
  status: PipelineRunStatus
}

export interface InferredCapability {
  name: string
  key: string
  description: string
  confidence: number
  supporting_evidence: string
  [key: string]: unknown
}

export interface ChangeSummaryCapability {
  name?: string
  key?: string
  confidence?: number
  description?: string
  change_description?: string
  change_type?: string
  supporting_evidence?: string
  old_key?: string
  old_name?: string
  new_name?: string
  [key: string]: unknown
}

export interface InferredSummary {
  artifact_id: number
  kind: string
  confidence: number
  is_old_project: boolean
  mode: string
  analysis_summary: string
  uncertain_questions: Array<{
    question: string
    context: string
    suggested_answer: string
    [key: string]: unknown
  }>
  inferred_capabilities: InferredCapability[]
  change_summary: {
    new_capabilities: ChangeSummaryCapability[]
    modified_capabilities: ChangeSummaryCapability[]
    removed_capabilities: ChangeSummaryCapability[]
    ui_only_changes: string
  } | null
  needs_confirmation: boolean
  provenance: Record<string, unknown>
  run_status: PipelineRunStatus
}

export interface SupplementSignalsRequest {
  confirmed_capabilities: Array<Record<string, unknown>>
  answers: Array<Record<string, unknown>>
  change_summary: Record<string, unknown> | null
  notes: string | null
}

export interface SupplementSignalsResponse {
  run_id: number
  capability_count: number
  answer_count: number
  has_change_summary: boolean
}

export const pipelineApi = {
  runPipeline: async (
    iterationId: number,
    data: PipelineRunRequest
  ): Promise<{ code: number; message: string; data: PipelineRunResponse }> => {
    return request.post(`/api/v1/pipeline/iteration/${iterationId}/run`, data)
  },

  getPipelineRun: async (
    runId: number
  ): Promise<{ code: number; message: string; data: PipelineRun }> => {
    return request.get(`/api/v1/pipeline/${runId}`)
  },

  resumePipeline: async (
    runId: number,
    data?: PipelineResumeRequest
  ): Promise<{ code: number; message: string; data: PipelineResumeResponse }> => {
    return request.post(`/api/v1/pipeline/${runId}/resume`, data || {})
  },

  getInferredSummary: async (
    runId: number
  ): Promise<{ code: number; message: string; data: InferredSummary }> => {
    return request.get(`/api/v1/pipeline/${runId}/inferred-summary`)
  },

  supplementSignals: async (
    runId: number,
    data: SupplementSignalsRequest
  ): Promise<{ code: number; message: string; data: SupplementSignalsResponse }> => {
    return request.put(`/api/v1/pipeline/${runId}/supplement-signals`, data)
  },
}

export default pipelineApi
