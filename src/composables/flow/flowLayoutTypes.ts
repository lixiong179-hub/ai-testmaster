export interface LayoutOptions {
  mainGapX: number
  branchGapY: number
  mainStartY: number
  branchStartY: number
  typeGapY: number
  nestedIndentX: number
  childrenHorizontalGap: number
  maxChildrenPerColumn: number
}

export const DEFAULT_LAYOUT_OPTIONS: LayoutOptions = {
  mainGapX: 280,
  branchGapY: 200,
  mainStartY: 0,
  branchStartY: 200,
  typeGapY: 60,
  nestedIndentX: 60,
  childrenHorizontalGap: 280,
  maxChildrenPerColumn: 4,
}

export const COMPACT_OPTIONS: Partial<LayoutOptions> = {
  mainGapX: 200,
  branchGapY: 140,
  branchStartY: 140,
  typeGapY: 40,
  nestedIndentX: 40,
  childrenHorizontalGap: 220,
  maxChildrenPerColumn: 5,
}

export type LayoutMode = 'standard' | 'compact' | 'type-layered' | 'focused-path'

export const LAYOUT_MODE_LABELS: Record<LayoutMode, string> = {
  standard: '标准布局',
  compact: '紧凑布局',
  'type-layered': '按类型分层',
  'focused-path': '仅整理当前路径',
}
