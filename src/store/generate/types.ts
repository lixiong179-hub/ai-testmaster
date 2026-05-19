import type { TestPoint } from '@/api/testPoint'

export interface GeneratedStep {
  step: number | string
  action: string
  param?: string
  expected_result?: string
  action_type?: string
  input_value?: string
  target_element?: string
  test_data?: Record<string, unknown>
  description?: string
  display_action?: string
  ui_elements?: Array<{ type?: string; label?: string }>
}

export interface GeneratedCase {
  id: number
  test_point_id: number | null
  test_point_label: string
  title: string
  module: string
  case_type: string
  test_category?: string
  precondition: string
  test_data?: Record<string, Record<string, string | number | boolean | null>>
  steps: GeneratedStep[]
  expected_result: string
  priority: number
  scene?: string
  ai_change_type?: 'added' | 'modified' | 'deprecated'
  parent_case_id?: number | null
  _error?: string
  _saved?: boolean
  _dbId?: number
}

export interface EditingCase {
  title: string
  module: string
  case_type: string
  test_category?: string
  precondition: string
  expected_result: string
  priority: number
  steps: GeneratedStep[]
  test_data?: Record<string, Record<string, string | number | boolean | null>>
  ai_change_type?: 'added' | 'modified' | 'deprecated'
  parent_case_id?: number | null
}

export interface ContextPreview {
  title: string
  type: string
  requirement?: string
  ui?: string
  uiSpecs?: number
  requirement_content?: string
  test_points?: TestPoint[]
}

export interface GenerateFormData {
  project_id: number | ''
  requirement_file_ids: number[]
  ui_file_ids: number[]
  ui_screen_ids: number[]
  test_point_ids: number[]
  test_points_data: TestPoint[]
  scene: string
  case_type: string
  exec_mode: 'all' | 'ui_auto' | 'manual'
  priority: number
  enhanced_mode: boolean
  extra_requirements: string
}

export interface SaveSingleCaseParam {
  id: number
  title?: string
  module?: string
  case_type?: string
  precondition?: string
  steps?: GeneratedStep[]
  expected_result?: string
  priority?: number
  test_category?: string
  test_data?: Record<string, unknown>
  parent_case_id?: number | null
  ai_change_type?: 'added' | 'modified' | 'deprecated'
  _saved?: boolean
  _dbId?: number
}

export interface StoreActions {
  nextCaseId: () => number
  handleSourceFileChange: () => void
  loadProjectFiles: () => Promise<void>
  loadUIPrototypeProjects: () => Promise<void>
  loadProjectCases: () => Promise<void>
  loadUIScreens: (uiPrototypeProjectId: number) => Promise<void>
  saveSingleCaseToDb: (c: SaveSingleCaseParam) => Promise<boolean>
  handleRegenerateCase: (index: number, skipConfirm?: boolean, preserveGenerating?: boolean) => Promise<void>
}

export const TEST_POINT_CACHE_MAX = 500

export function generateCaseNo(projectId: number | '', extraSuffix?: number): string {
  const ts = Date.now()
  const rand = Math.random().toString(36).substring(2, 8)
  const suffix = extraSuffix != null ? `-${extraSuffix}` : ''
  return `CASE${String(projectId)}-${ts}-${rand}${suffix}`
}

export function normalizePriority(priority: unknown): number {
  if (typeof priority === 'number') {
    if (priority < 1) return 1
    if (priority > 3) return 3
    return priority
  }
  const pMap: Record<string, number> = {
    P0: 1,
    P1: 1,
    P2: 2,
    P3: 3,
    high: 1,
    medium: 2,
    low: 3,
    '1': 1,
    '2': 2,
    '3': 3,
  }
  return pMap[String(priority)] || 2
}

export function extractListItems(res: unknown): unknown[] {
  if (!res || typeof res !== 'object') return []
  if (Array.isArray(res)) return res
  if (Array.isArray((res as Record<string, unknown>).items)) {
    return (res as Record<string, unknown>).items as unknown[]
  }
  const d = (res as Record<string, unknown>).data
  if (d && typeof d === 'object' && Array.isArray((d as Record<string, unknown>).items)) {
    return (d as Record<string, unknown>).items as unknown[]
  }
  return []
}
