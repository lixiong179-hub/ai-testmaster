import { type Component } from 'vue'
import {
    HomeFilled,
    Setting,
    Message,
    Check,
    Timer,
    Document,
    Lightning,
    Odometer,
} from '@element-plus/icons-vue'
import { hasPermission } from '@/directives/permission'

export interface MenuItem {
    index: string
    label: string
    icon?: Component
    permission?: string
    children?: MenuItem[]
}

// 一级菜单 8 项：快速测试 / 项目中心 / 资源中心 / 测试资产 / 执行中心 / 评审中心 / 运营看板 / 系统管理
// 轻量页面合并入父级子菜单，迭代中心拆分（迭代管理归资源中心、评审 Inbox 独立为评审中心）
export const MENU_CONFIG: MenuItem[] = [
    // 快速测试：网址驱动一键编排，置顶以便用户最快触达
    { index: '/home/quick-test', label: '快速测试', icon: Lightning },
    { index: '/home/project', label: '项目中心', icon: HomeFilled },
    // 资源中心：合并文件管理、迭代管理、需求分析与 UI 原型，统一资源入口
    {
        index: 'resource',
        label: '资源中心',
        icon: Message,
        children: [
            { index: '/home/requirement', label: '文件管理' },
            { index: '/home/iteration/list', label: '迭代管理' },
            { index: '/home/requirement/analysis', label: '需求分析' },
            { index: '/home/requirement/ui-prototype', label: 'UI原型' },
        ],
    },
    {
        index: 'case',
        label: '测试资产',
        icon: Check,
        children: [
            { index: '/home/case', label: '用例列表' },
            { index: '/home/case/test-point-management', label: '测试点管理' },
            { index: '/home/case/smart-generate', label: '智能生成用例' },
            { index: '/home/case/migration', label: '用例迁移' },
            { index: '/home/case/case-refresh', label: '保鲜建议' },
        ],
    },
    // 执行中心：合并任务列表、报告中心与缺陷管理，统一测试执行入口
    // 任务列表保留 /home/task 路径（其子路由众多，不迁移以最小化变动）；报告/缺陷迁至 /home/execution/*
    {
        index: 'execution',
        label: '执行中心',
        icon: Timer,
        children: [
            { index: '/home/task', label: '任务列表' },
            { index: '/home/execution/report', label: '报告中心' },
            { index: '/home/execution/bug', label: '缺陷管理' },
        ],
    },
    // 评审中心：独立一级菜单，聚焦用例评审 Inbox（路径沿用 /home/iteration/review）
    {
        index: 'review',
        label: '评审中心',
        icon: Document,
        children: [
            { index: '/home/iteration/review/0', label: '评审 Inbox' },
        ],
    },
    // 运营看板：跨项目的流水线与成本监控仪表盘，与具体迭代无关，独立分组
    {
        index: 'ops',
        label: '运营看板',
        icon: Odometer,
        children: [
            { index: '/home/pipeline-dashboard', label: 'Pipeline仪表盘' },
            { index: '/home/ai-cost-dashboard', label: 'AI成本仪表盘' },
            { index: '/home/self-healing/audits', label: '自愈审计' },
            { index: '/home/ab-test-dashboard', label: 'A/B实验看板' },
        ],
    },
    // 系统管理：精简为用户/角色/审计日志/FeatureFlag/Prompt模板；质量规则、测试能力移出菜单（路由暂留待 Task 8/9）
    {
        index: 'system',
        label: '系统管理',
        icon: Setting,
        children: [
            { index: '/home/system/user', label: '用户管理', permission: 'user:list' },
            { index: '/home/system/role', label: '角色管理', permission: 'role:list' },
            { index: '/home/system/audit-log', label: '审计日志', permission: 'system:manage' },
            { index: '/home/system/feature-flag', label: 'FeatureFlag管理', permission: 'system:manage' },
            { index: '/home/system/prompt-template', label: 'Prompt模板管理', permission: 'system:manage' },
        ],
    },
]

// 按权限过滤菜单：无权限的叶子节点剔除，子菜单全部不可见时父菜单一并隐藏
export function filterMenuByPermission(items: MenuItem[]): MenuItem[] {
    return items
        .map((item) => {
            if (!hasPermission(item.permission)) return null
            if (item.children) {
                const filteredChildren = filterMenuByPermission(item.children)
                if (filteredChildren.length === 0) return null
                return { ...item, children: filteredChildren }
            }
            return item
        })
        .filter((item): item is MenuItem => item !== null)
}

// 面包屑路径映射：以路径前缀为键，updateBreadcrumb 按路径分段逐级查找
export const breadcrumbMap: Record<string, string> = {
    '/home/dashboard': '仪表盘',
    '/home/workbench': '工作台',
    '/home/quick-test': '快速测试',
    '/home/project': '项目中心',
    '/home/project/detail': '项目详情',
    // 资源中心
    '/home/requirement': '资源中心',
    '/home/requirement/upload': '上传资源',
    '/home/requirement/analysis': '需求分析',
    '/home/requirement/ui-prototype': 'UI原型详情',
    // 测试资产
    '/home/case': '测试资产',
    '/home/case/detail': '用例详情',
    '/home/case/test-point-management': '测试点管理',
    '/home/case/test-point-extract': '测试点提取',
    '/home/case/smart-generate': '智能生成用例',
    '/home/case/migration': '用例迁移',
    '/home/case/case-refresh': '保鲜建议',
    '/home/case/quality': '用例质量分析',
    '/home/case/iteration/regression-generate': '回归变更分析',
    // 执行中心
    '/home/task': '执行中心',
    '/home/task/list': '任务列表',
    '/home/task/create': '创建任务',
    '/home/task/detail': '任务详情',
    '/home/task/execution': '测试执行',
    '/home/execution': '执行中心',
    '/home/execution/report': '报告中心',
    '/home/execution/report/detail': '报告详情',
    '/home/execution/bug': '缺陷管理',
    // 评审中心（路径沿用 /home/iteration/review）
    '/home/iteration/review': '评审 Inbox',
    // 运营看板
    '/home/pipeline-dashboard': 'Pipeline仪表盘',
    '/home/ai-cost-dashboard': 'AI成本仪表盘',
    '/home/ab-test-dashboard': 'A/B实验看板',
    '/home/self-healing/audits': '自愈审计',
    // 迭代相关（路径保留，菜单不再展示迭代中心父级）
    '/home/iteration/list': '迭代管理',
    '/home/iteration/pipeline': 'Pipeline进度',
    '/home/iteration/regression-generate': '回归变更分析',
    // 系统管理
    '/home/system': '系统管理',
    '/home/system/user': '用户管理',
    '/home/system/role': '角色管理',
    '/home/system/audit-log': '审计日志',
    '/home/system/test-capability': '测试能力',
    '/home/system/quality-rule': '质量规则配置',
    '/home/system/feature-flag': 'FeatureFlag管理',
    '/home/system/prompt-template': 'Prompt模板管理',
    '/home/system/profile': '个人中心',
}
