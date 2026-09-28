import { describe, it, expect } from 'vitest'
import { routes } from '../routes'

// UIPrototypeManage 路由位于 Home -> requirement -> ui-prototype
function findUIPrototypeRoute() {
  const homeRoute = routes.find((r) => r.name === 'Home')
  const requirementRoute = homeRoute?.children?.find((c) => c.path === 'requirement')
  return requirementRoute?.children?.find((c) => c.path === 'ui-prototype')
}

// beforeEnter 守卫类型断言：仅依赖 to.query，返回重定向对象或 undefined
type BeforeEnterGuard = (to: { query: Record<string, unknown> }) => unknown

describe('UIPrototypeManage 路由 beforeEnter 守卫', () => {
  const route = findUIPrototypeRoute()
  const beforeEnter = route?.beforeEnter as BeforeEnterGuard | undefined

  it('路由配置存在且包含 beforeEnter 守卫', () => {
    expect(route).toBeDefined()
    expect(beforeEnter).toBeDefined()
  })

  it('无参数时重定向到资源中心并筛选UI原型类型', () => {
    const result = beforeEnter!({ query: {} })
    expect(result).toEqual({
      name: 'RequirementResource',
      query: { resource_type: 'ui_mockup' },
    })
  })

  it('参数齐全时放行（返回 undefined）', () => {
    const result = beforeEnter!({
      query: { project_id: '1', prototype_project_id: '2' },
    })
    expect(result).toBeUndefined()
  })

  it('只有 project_id 无 prototype_project_id 时重定向', () => {
    const result = beforeEnter!({ query: { project_id: '1' } })
    expect(result).toEqual({
      name: 'RequirementResource',
      query: { resource_type: 'ui_mockup' },
    })
  })

  it('只有 prototype_project_id 无 project_id 时重定向', () => {
    const result = beforeEnter!({ query: { prototype_project_id: '2' } })
    expect(result).toEqual({
      name: 'RequirementResource',
      query: { resource_type: 'ui_mockup' },
    })
  })

  it('参数为空字符串时重定向', () => {
    const result = beforeEnter!({
      query: { project_id: '', prototype_project_id: '' },
    })
    expect(result).toEqual({
      name: 'RequirementResource',
      query: { resource_type: 'ui_mockup' },
    })
  })
})
