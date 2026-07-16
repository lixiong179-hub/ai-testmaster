import request from '@/utils/request'
import type { TestCase } from '@/types/testCase'

export type DeviceType = 'tablet' | 'phone' | 'desktop' | 'web'
export type MigrationType = 'cloned' | 'adapted' | 'split' | 'new' | 'deprecated'

export interface MigrationPreviewCase {
  title: string
  module?: string
  precondition?: string
  steps?: Array<Record<string, unknown>>
  expected_result?: string
  priority?: number
}

export interface MigrationPreviewItem {
  batch_id: string
  source_case_id: number
  migration_type: MigrationType
  confidence: number
  preview_cases: MigrationPreviewCase[]
  step_changes: Array<Record<string, unknown>>
  warnings: string[]
  errors: string[]
}

export interface MigrationPreviewResponse {
  batch_id: string
  source_device: DeviceType
  target_device: DeviceType
  summary: {
    total: number
    success: number
    failed: number
    cloned: number
    adapted: number
    split: number
    new: number
    deprecated: number
  }
  items: MigrationPreviewItem[]
}

export interface MigrationCommitResponse {
  success: boolean
  batch_id: string
  created_case_ids: number[]
  errors: string[]
}

export interface MigrationBatchResponse {
  batch_id: string
  case_count: number
  case_ids: number[]
}

export interface ExcelImportResponse {
  imported_count: number
  imported_case_ids: number[]
}

export const caseMigrationApi = {
  importExcel: async (payload: {
    file: File
    projectId: number
    targetDevice: DeviceType
  }): Promise<ExcelImportResponse> => {
    const formData = new FormData()
    formData.append('file', payload.file)
    formData.append('project_id', String(payload.projectId))
    formData.append('target_device', payload.targetDevice)
    const response = await request.post('/api/v1/case-migration/import-excel', formData)
    return (response.data || response) as ExcelImportResponse
  },

  previewBatch: async (payload: {
    sourceCaseIds: number[]
    sourceDevice: DeviceType
    targetDevice: DeviceType
    targetProjectId: number
    targetUiSpecs: string
  }): Promise<MigrationPreviewResponse> => {
    const response = await request.post('/api/v1/case-migration/preview-batch', {
      source_case_ids: payload.sourceCaseIds,
      source_device: payload.sourceDevice,
      target_device: payload.targetDevice,
      target_project_id: payload.targetProjectId,
      target_ui_specs: payload.targetUiSpecs,
    })
    return (response.data || response) as MigrationPreviewResponse
  },

  commitBatch: async (payload: {
    batchId: string
    targetProjectId: number
    targetDevice: DeviceType
    items: MigrationPreviewItem[]
  }): Promise<MigrationCommitResponse> => {
    const response = await request.post('/api/v1/case-migration/commit-batch', {
      batch_id: payload.batchId,
      target_project_id: payload.targetProjectId,
      target_device: payload.targetDevice,
      items: payload.items,
    })
    return (response.data || response) as MigrationCommitResponse
  },

  getBatch: async (batchId: string): Promise<MigrationBatchResponse> => {
    const response = await request.get(`/api/v1/case-migration/batches/${batchId}`)
    return (response.data || response) as MigrationBatchResponse
  },

  rollbackBatch: async (batchId: string): Promise<MigrationBatchResponse> => {
    const response = await request.post(`/api/v1/case-migration/batches/${batchId}/rollback`)
    return (response.data || response) as MigrationBatchResponse
  },
}

export function summarizeUiSpecs(
  screens: Array<{ screen_name: string; summary?: string }>
): string {
  return screens
    .map((screen, index) => `${index + 1}. ${screen.screen_name}: ${screen.summary || '无摘要'}`)
    .join('\n')
}

export function caseOptionLabel(testCase: TestCase): string {
  return `${testCase.case_no || testCase.id} - ${testCase.title}`
}
