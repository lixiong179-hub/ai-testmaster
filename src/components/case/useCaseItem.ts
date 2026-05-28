import { computed } from 'vue'
import type { TestCase } from '@/types/testCase'
import type { TagType } from '@/types/element-plus'

const CASE_TYPE_MAP: Record<string, { label: string; tagType: TagType }> = {
  ui_automation: { label: 'UI自动化', tagType: 'success' },
  manual: { label: '手工测试', tagType: 'info' },
  api_automation: { label: 'API自动化', tagType: 'primary' },
  performance: { label: '性能测试', tagType: 'warning' },
  security: { label: '安全测试', tagType: 'danger' },
  UI: { label: 'UI自动化', tagType: 'success' },
  API: { label: 'API自动化', tagType: 'primary' },
  功能: { label: '手工测试', tagType: 'info' },
  功能测试: { label: '手工测试', tagType: 'info' },
  functional: { label: '手工测试', tagType: 'info' },
  接口: { label: 'API自动化', tagType: 'primary' },
}

const LIFECYCLE_STATUS_MAP: Record<string, { label: string; type: TagType }> = {
  draft: { label: '草稿', type: 'info' },
  active: { label: '可用', type: 'success' },
  pending_review: { label: '评审中', type: 'primary' },
  needs_modify: { label: '待修改', type: 'warning' },
  locator_broken: { label: '待重录', type: 'danger' },
  deprecated: { label: '已弃用', type: 'info' },
  archived: { label: '已归档', type: 'info' },
}

export function useCaseItem(props: { caseItem: TestCase }) {
  const lifecycleTag = computed(() => {
    const status = props.caseItem.lifecycle_status
    if (!status || status === 'active' || status === 'archived') return null
    return LIFECYCLE_STATUS_MAP[status] || null
  })

  const caseTypeLabel = computed(() => {
    const type = props.caseItem.case_type || ''
    return CASE_TYPE_MAP[type]?.label || type
  })

  const caseTypeTagType = computed(() => {
    const type = props.caseItem.case_type || ''
    return CASE_TYPE_MAP[type]?.tagType || 'info'
  })

  const priorityText = (priority: number | undefined): string => {
    const map: Record<number, string> = { 1: '高', 2: '中', 3: '低' }
    return map[priority ?? 2] || '中'
  }

  const statusText = (status: number | undefined): string => {
    const map: Record<number, string> = { 0: '生成中', 1: '生成成功', 2: '生成失败' }
    return map[status ?? 0] || '未知'
  }

  const statusClass = (status: number | undefined): string => {
    const map: Record<number, string> = {
      0: 'status-processing',
      1: 'status-success',
      2: 'status-failed',
    }
    return map[status ?? 0] || ''
  }

  const formatTime = (time: string | undefined): string => {
    if (!time) return ''
    return new Date(time).toLocaleString()
  }

  return {
    lifecycleTag,
    caseTypeLabel,
    caseTypeTagType,
    priorityText,
    statusText,
    statusClass,
    formatTime,
  }
}
