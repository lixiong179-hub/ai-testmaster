export interface LayoutOptions {
  mainGapX: number
  branchGapY: number
  mainStartY: number
  branchStartY: number
  typeGapY: number
  nestedIndentX: number
  childrenHorizontalGap: number
  maxChildrenPerColumn: number
  maxMainPerRow: number
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
  maxMainPerRow: 8,
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

export type LayoutMode = 'standard' | 'compact' | 'type-layered' | 'focused-path' | 'swimlane'

export const LAYOUT_MODE_LABELS: Record<LayoutMode, string> = {
  standard: '标准布局',
  compact: '紧凑布局',
  'type-layered': '按类型分层',
  'focused-path': '仅整理当前路径',
  swimlane: '泳道布局',
}

export const SWIMLANE_OPTIONS: Partial<LayoutOptions> = {
  mainGapX: 260,
  branchGapY: 180,
  branchStartY: 180,
  typeGapY: 40,
  nestedIndentX: 40,
  childrenHorizontalGap: 240,
  maxChildrenPerColumn: 4,
  maxMainPerRow: 6,
}
