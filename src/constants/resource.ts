/**
 * 资源管理模块常量配置
 * 集中管理硬编码值，便于维护和修改
 */

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
  { label: '规划中', value: 'planning' },
  { label: '进行中', value: 'active' },
  { label: '已完成', value: 'completed' },
  { label: '已归档', value: 'archived' },
] as const

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
