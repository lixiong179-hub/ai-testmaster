import { describe, it, expect } from 'vitest'
import { MENU_CONFIG, type MenuItem } from '../menuConfig'

// 菜单精简重构（Task 7）：一级菜单 11→8，合并轻量页面、拆分迭代中心、独立评审中心
// 本测试直接校验静态 MENU_CONFIG 结构，不依赖权限与路由环境

function findTopMenu(label: string): MenuItem | undefined {
    return MENU_CONFIG.find((item) => item.label === label)
}

function childLabels(menu: MenuItem | undefined): string[] {
    if (!menu?.children) return []
    return menu.children.map((c) => c.label)
}

function topLabels(): string[] {
    return MENU_CONFIG.map((item) => item.label)
}

describe('MENU_CONFIG 菜单精简 11→8', () => {
    it('一级菜单数量为 8', () => {
        expect(MENU_CONFIG).toHaveLength(8)
    })

    it('一级菜单顺序与名称符合目标结构', () => {
        expect(topLabels()).toEqual([
            '快速测试',
            '项目中心',
            '资源中心',
            '测试资产',
            '执行中心',
            '评审中心',
            '运营看板',
            '系统管理',
        ])
    })

    it('资源中心含子菜单：文件管理、迭代管理、需求分析、UI原型', () => {
        const resource = findTopMenu('资源中心')
        expect(resource).toBeDefined()
        expect(childLabels(resource)).toEqual([
            '文件管理',
            '迭代管理',
            '需求分析',
            'UI原型',
        ])
    })

    it('需求分析从独立一级菜单移至资源中心子菜单', () => {
        // 需求分析不再是顶级菜单
        expect(findTopMenu('需求分析')).toBeUndefined()
        // 而是资源中心的子菜单
        const resource = findTopMenu('资源中心')
        expect(resource?.children?.some((c) => c.label === '需求分析')).toBe(true)
    })

    it('执行中心含子菜单：任务列表、报告中心、缺陷管理', () => {
        const execution = findTopMenu('执行中心')
        expect(execution).toBeDefined()
        expect(childLabels(execution)).toEqual(['任务列表', '报告中心', '缺陷管理'])
    })

    it('缺陷管理与报告中心从独立一级菜单移至执行中心子菜单', () => {
        expect(findTopMenu('缺陷管理')).toBeUndefined()
        expect(findTopMenu('报告中心')).toBeUndefined()
        const execution = findTopMenu('执行中心')
        expect(execution?.children?.some((c) => c.label === '缺陷管理')).toBe(true)
        expect(execution?.children?.some((c) => c.label === '报告中心')).toBe(true)
    })

    it('评审中心为独立一级菜单且含评审 Inbox 子菜单', () => {
        const review = findTopMenu('评审中心')
        expect(review).toBeDefined()
        expect(review?.children).toBeDefined()
        expect(childLabels(review)).toEqual(['评审 Inbox'])
    })

    it('迭代中心一级菜单已移除', () => {
        expect(findTopMenu('迭代中心')).toBeUndefined()
    })

    it('系统管理移除质量规则配置与测试能力', () => {
        const system = findTopMenu('系统管理')
        expect(system).toBeDefined()
        const labels = childLabels(system)
        expect(labels).not.toContain('质量规则配置')
        expect(labels).not.toContain('测试能力')
        // 保留项仍存在
        expect(labels).toEqual([
            '用户管理',
            '角色管理',
            '审计日志',
            'FeatureFlag管理',
            'Prompt模板管理',
        ])
    })

    it('测试资产子菜单保持不变', () => {
        const testCase = findTopMenu('测试资产')
        expect(childLabels(testCase)).toEqual([
            '用例列表',
            '测试点管理',
            '智能生成用例',
            '用例迁移',
            '保鲜建议',
        ])
    })

    it('运营看板子菜单保持不变', () => {
        const ops = findTopMenu('运营看板')
        expect(childLabels(ops)).toEqual([
            'Pipeline仪表盘',
            'AI成本仪表盘',
            '自愈审计',
            'A/B实验看板',
        ])
    })

    it('执行中心子菜单路径指向新的执行中心归口', () => {
        const execution = findTopMenu('执行中心')
        const report = execution?.children?.find((c) => c.label === '报告中心')
        const bug = execution?.children?.find((c) => c.label === '缺陷管理')
        const task = execution?.children?.find((c) => c.label === '任务列表')
        expect(report?.index).toBe('/home/execution/report')
        expect(bug?.index).toBe('/home/execution/bug')
        // 任务列表沿用 /home/task（不迁移以最小化子路由变动）
        expect(task?.index).toBe('/home/task')
    })

    it('需求分析子菜单路径指向资源中心需求分析路由', () => {
        const resource = findTopMenu('资源中心')
        const analysis = resource?.children?.find((c) => c.label === '需求分析')
        expect(analysis?.index).toBe('/home/requirement/analysis')
    })

    it('评审 Inbox 路径沿用 /home/iteration/review（保留旧路径）', () => {
        const review = findTopMenu('评审中心')
        const inbox = review?.children?.find((c) => c.label === '评审 Inbox')
        expect(inbox?.index).toBe('/home/iteration/review/0')
    })
})
