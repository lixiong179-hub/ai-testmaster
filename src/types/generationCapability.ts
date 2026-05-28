export type GenerationCapabilityMode =
  | 'new_full_generation'
  | 'new_light_generation'
  | 'ui_change_regression'
  | 'requirement_change_regression'
  | 'cross_device_migration'

export type RegressionChangeSource = 'ui_flow' | 'requirement' | 'mixed'

export interface GenerationContextQuality {
  mode: GenerationCapabilityMode
  title: string
  description: string
  requirementCount: number
  testPointCount: number
  uiScreenCount: number
  hasPageFlow: boolean
  historyCaseCount: number
  warnings: string[]
  missing: string[]
  sourceTags: string[]
}

export function getGenerationCapabilityQuality(params: {
  requirementCount: number
  testPointCount: number
  uiScreenCount: number
  hasPageFlow: boolean
  historyCaseCount: number
}): GenerationContextQuality {
  const { requirementCount, testPointCount, uiScreenCount, hasPageFlow, historyCaseCount } = params
  const hasRequirement = requirementCount > 0
  const hasTestPoint = testPointCount > 0
  const hasUi = uiScreenCount > 0
  const sourceTags: string[] = []
  const warnings: string[] = []
  const missing: string[] = []

  if (hasRequirement) sourceTags.push('需求约束')
  if (hasTestPoint) sourceTags.push('测试点覆盖')
  if (hasUi) sourceTags.push('UI页面关联')
  if (hasPageFlow) sourceTags.push('页面流转路径')
  if (historyCaseCount > 0) sourceTags.push('历史用例参考')

  if (hasRequirement && hasTestPoint && hasUi) {
    if (!hasPageFlow) warnings.push('未检测到页面流转，复杂页面跳转和跨页面路径覆盖会下降')
    return {
      mode: 'new_full_generation',
      title: '完整上下文生成',
      description: '适合生成贴合项目的高质量功能、UI自动化和端到端专项用例。',
      requirementCount,
      testPointCount,
      uiScreenCount,
      hasPageFlow,
      historyCaseCount,
      warnings,
      missing,
      sourceTags,
    }
  }

  if (hasRequirement && hasTestPoint) {
    return {
      mode: 'new_light_generation',
      title: '轻量生成',
      description: '适合业务规则、接口逻辑和无强 UI 依赖的功能用例。',
      requirementCount,
      testPointCount,
      uiScreenCount,
      hasPageFlow,
      historyCaseCount,
      warnings,
      missing,
      sourceTags,
    }
  }

  if (!hasRequirement) missing.push('需求文档')
  if (!hasTestPoint) missing.push('测试点')
  if (!hasUi) warnings.push('未选择 UI 原型，生成结果不会包含页面元素和流转路径')

  return {
    mode: 'new_light_generation',
    title: '上下文待补齐',
    description: '建议补齐需求文档和测试点后再生成，以提升用例边界和断言质量。',
    requirementCount,
    testPointCount,
    uiScreenCount,
    hasPageFlow,
    historyCaseCount,
    warnings,
    missing,
    sourceTags,
  }
}
