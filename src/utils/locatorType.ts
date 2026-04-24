/**
 * 定位类型辅助函数
 * 提供定位类型的标签显示和标签样式映射
 */

/**
 * 获取定位类型的中文标签
 * @param type 定位类型标识
 * @returns 中文标签文本
 */
export const getLocatorTypeLabel = (type: string): string => {
  const labels: Record<string, string> = {
    vision: '视觉模型',
    role: 'ARIA角色',
    text: '文本定位',
    css: 'CSS选择器',
    ref: '引用定位',
    xpath: 'XPath',
  }
  return labels[type] || type
}

/**
 * 获取定位类型对应的 Element Plus Tag 组件类型
 * @param type 定位类型标识
 * @returns Tag 组件的 type 属性值
 */
export const getLocatorTypeTagType = (type: string): string => {
  const types: Record<string, string> = {
    vision: 'warning',
    role: 'success',
    text: 'success',
    css: '',
    ref: 'info',
    xpath: '',
  }
  return types[type] || 'info'
}
