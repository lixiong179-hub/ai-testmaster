/**
 * 资源管理模块常量配置
 * 集中管理硬编码值，便于维护和修改
 */
import type { TagType } from '@/types/element-plus'

export const RESOURCE_CONFIG = {
  /** 默认每页显示条数 */
  DEFAULT_PAGE_SIZE: 10,

  /** 分页大小选项 */
  PAGE_SIZE_OPTIONS: [10, 20, 50, 100] as const,

  /** 批量上传最大文件数 */
  MAX_BATCH_UPLOAD: 20,

  /** 前端"未分类"标识（对应 iteration_id = 0 或 NULL） */
  ITERATION_UNCLASSIFIED: 0 as const,

  /** 前端"全部"标识（对应 selectedIterationId = null） */
  ITERATION_ALL: null,

  /** 后端"未分类"筛选参数值（-1 表示筛选 iteration_id 为 NULL 的资源） */
  BACKEND_UNCLASSIFIED_PARAM: -1 as const,
}

/** 资源类型选项 */
export const RESOURCE_TYPE_OPTIONS = [
  { label: '需求文档', value: 'requirement' },
  { label: 'UI原型图', value: 'ui_mockup' },
  { label: 'API文档', value: 'api_doc' },
  { label: '测试数据', value: 'test_data' },
  { label: '其他文件', value: 'other' },
] as const

/** 迭代状态选项 */
export const ITERATION_STATUS_OPTIONS = [
  { label: '草稿', value: 'draft' },
  { label: '流水线运行中', value: 'in_pipeline' },
  { label: '待评审', value: 'in_review' },
  { label: '已定稿', value: 'finalized' },
  { label: '已归档', value: 'archived' },
] as const

/**
 * 测试用例生命周期状态选项（与后端 TestCaseLifecycleStatus 对齐）
 *
 * 顺序与后端字段注释一致：
 * draft / active / pending_review / needs_modify / locator_broken / deprecated / archived
 * 注意：历史值 `reviewed` 已废弃，不再出现在选项中。
 */
export const LIFECYCLE_STATUS_OPTIONS = [
  { label: '草稿', value: 'draft' },
  { label: '已激活', value: 'active' },
  { label: '待审核', value: 'pending_review' },
  { label: '需修改', value: 'needs_modify' },
  { label: '定位失效', value: 'locator_broken' },
  { label: '已弃用', value: 'deprecated' },
  { label: '已归档', value: 'archived' },
] as const

/** 生命周期状态对应的 Element Plus Tag 类型 */
export const LIFECYCLE_STATUS_TAG_MAP: Record<string, TagType> = {
  draft: 'info',
  active: 'success',
  pending_review: 'warning',
  needs_modify: 'danger',
  locator_broken: 'danger',
  deprecated: 'info',
  archived: 'info',
}

/**
 * 获取生命周期状态的中文文案
 * @param status 状态值；空值返回占位符 `-`，未知状态回退为原始值
 */
export function getLifecycleStatusLabel(status?: string | null): string {
  if (!status) {
    return '-'
  }
  const opt = LIFECYCLE_STATUS_OPTIONS.find((o) => o.value === status)
  return opt?.label ?? status
}

/**
 * 获取生命周期状态对应的 Tag 类型
 * @param status 状态值；空值或未知状态统一返回 `info`
 */
export function getLifecycleStatusTagType(status?: string | null): TagType {
  if (!status) {
    return 'info'
  }
  return LIFECYCLE_STATUS_TAG_MAP[status] ?? 'info'
}

/** 单文件上传支持的格式 */
export const SINGLE_FILE_ACCEPT =
  '.txt,.doc,.docx,.pdf,.md,.xlsx,.xls,.csv,.json,.yaml,.yml,.png,.jpg,.jpeg,.gif,.zip,.rar'

/** 批量上传支持的格式（UI原型图） */
export const BATCH_FILE_ACCEPT = '.png,.jpg,.jpeg,.gif,.webp,.bmp,.zip'

/** XMind 导入配置常量（与后端 MAX_FILE_SIZE 保持一致） */
export const XMIND_IMPORT_CONFIG = {
  /** 最大文件大小（字节），对应后端 10MB */
  MAX_FILE_SIZE: 10 * 1024 * 1024,
  /** 支持的文件扩展名 */
  ACCEPT: '.xmind',
  /** 文件大小提示文本 */
  SIZE_HINT: '文件大小不超过 10MB',
} as const

/** 资源类型关键词映射 - 文件名中包含这些关键词时自动归类到对应资源类型 */
const RESOURCE_TYPE_KEYWORDS: Record<string, string[]> = {
  requirement: ['需求', 'requirement', 'spec', '规格', 'prd', 'brd'],
  ui_mockup: ['ui', '原型', 'mockup', '设计', 'design', 'figma', 'axure'],
  api_doc: ['api', '接口', 'swagger', 'openapi'],
  test_data: ['测试数据', 'testdata'],
}

/** 扩展名到资源类型的默认映射 - 当文件名无关键词匹配时的回退策略 */
const EXTENSION_RESOURCE_MAP: Record<string, string> = {
  docx: 'requirement',
  doc: 'requirement',
  pdf: 'requirement',
  txt: 'requirement',
  md: 'requirement',
  png: 'ui_mockup',
  jpg: 'ui_mockup',
  jpeg: 'ui_mockup',
  gif: 'ui_mockup',
  webp: 'ui_mockup',
  yaml: 'api_doc',
  yml: 'api_doc',
  json: 'api_doc',
  xlsx: 'test_data',
  xls: 'test_data',
  csv: 'test_data',
}

/**
 * 根据文件名自动识别资源类型
 * 优先级：文件名关键词 > 扩展名默认映射 > other
 * 与后端 app.utils.file_utils.detect_resource_type 逻辑保持一致
 */
export function detectResourceType(filename: string): string {
  const filenameLower = filename.toLowerCase()
  for (const [resourceType, keywords] of Object.entries(RESOURCE_TYPE_KEYWORDS)) {
    if (keywords.some((keyword) => filenameLower.includes(keyword))) {
      return resourceType
    }
  }
  const ext = filename.includes('.') ? filename.split('.').pop()!.toLowerCase() : ''
  return EXTENSION_RESOURCE_MAP[ext] || 'other'
}

/** 资源类型对应的 Element Plus Tag 类型 */
export const RESOURCE_TYPE_TAG_MAP: Record<string, TagType> = {
  requirement: 'primary',
  ui_mockup: 'success',
  api_doc: 'warning',
  test_data: 'info',
  other: 'info',
}

/** 获取资源类型显示标签 */
export function getResourceTypeLabel(type: string): string {
  const opt = RESOURCE_TYPE_OPTIONS.find((o) => o.value === type)
  return opt?.label ?? '其他文件'
}
