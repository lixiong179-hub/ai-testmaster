import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import type { Project, ProjectListResponse, ProjectDetailResponse } from '@/api/project'

// Task1: 屏蔽外部依赖，聚焦 store 纯逻辑与全局上下文行为
vi.mock('element-plus', () => ({
    ElMessage: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))
vi.mock('@/api/project', () => ({
    ProjectAPI: {
        getProjectList: vi.fn(),
        getProjectDetail: vi.fn(),
        createProject: vi.fn(),
        deleteProject: vi.fn(),
        getProjectConfig: vi.fn(),
        updateProjectConfig: vi.fn(),
    },
}))
vi.mock('@/api/file', () => ({
    FileAPI: {
        uploadFile: vi.fn(),
        submitUrl: vi.fn(),
        deleteFile: vi.fn(),
    },
}))

import { useProjectStore } from '../project'
import { ProjectAPI } from '@/api/project'
import { resolveInitialProjectId } from '@/views/project/useProjectDetail'

/** 构造完整 Project，避免缺字段触发 TS 与运行时校验问题 */
function makeProject(overrides: Partial<Project> = {}): Project {
    return {
        id: 1,
        name: '默认项目',
        description: '',
        project_type: 'web',
        status: 1,
        create_time: '2026-07-30 10:00:00',
        update_time: '2026-07-30 10:00:00',
        source: 'manual',
        ...overrides,
    }
}

function makeListResponse(items: Project[]): ProjectListResponse {
    return {
        code: 200,
        message: 'ok',
        data: { items, total: items.length, page: 1, page_size: 100 },
    }
}

function makeDetailResponse(project: Project): ProjectDetailResponse {
    return {
        code: 200,
        message: 'ok',
        data: { ...project, files: [] },
    }
}

describe('useProjectStore - 全局项目上下文 currentProjectId (Task1)', () => {
    let store: ReturnType<typeof useProjectStore>

    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
        store = useProjectStore()
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('setCurrentProject', () => {
        it('正确更新 currentProjectId', () => {
            store.setCurrentProject(42)
            expect(store.currentProjectId).toBe(42)
        })

        it('支持清空为 null', () => {
            store.setCurrentProject(42)
            store.setCurrentProject(null)
            expect(store.currentProjectId).toBeNull()
        })

        it('覆盖式更新：后值替换前值', () => {
            store.setCurrentProject(1)
            store.setCurrentProject(2)
            expect(store.currentProjectId).toBe(2)
        })
    })

    describe('currentProjectName getter', () => {
        it('基于 currentProjectId 从 projects 列表查找名称', async () => {
            vi.mocked(ProjectAPI.getProjectList).mockResolvedValueOnce(
                makeListResponse([makeProject({ id: 1, name: '项目A' }), makeProject({ id: 2, name: '项目B' })])
            )
            await store.fetchProjects()
            store.setCurrentProject(2)
            expect(store.currentProjectName).toBe('项目B')
        })

        it('项目不存在时返回空字符串', () => {
            store.projects = [makeProject({ id: 1, name: '项目A' })]
            store.setCurrentProject(999)
            expect(store.currentProjectName).toBe('')
        })

        it('currentProjectId 为 null 时返回空字符串', () => {
            store.projects = [makeProject({ id: 1, name: '项目A' })]
            store.setCurrentProject(null)
            expect(store.currentProjectName).toBe('')
        })

        it('currentProject 存在时优先返回其名称', () => {
            store.currentProject = makeProject({ id: 1, name: '当前详情项目' })
            store.setCurrentProject(1)
            expect(store.currentProjectName).toBe('当前详情项目')
        })
    })

    describe('fetchProjectDetail 同步全局上下文', () => {
        it('获取详情后同步 currentProjectId', async () => {
            vi.mocked(ProjectAPI.getProjectDetail).mockResolvedValueOnce(
                makeDetailResponse(makeProject({ id: 7, name: '详情项目' }))
            )
            await store.fetchProjectDetail(7)
            expect(store.currentProjectId).toBe(7)
            expect(store.currentProject?.id).toBe(7)
        })

        it('详情获取失败时不清空已有 currentProjectId', async () => {
            store.setCurrentProject(5)
            vi.mocked(ProjectAPI.getProjectDetail).mockRejectedValueOnce(new Error('网络错误'))
            await store.fetchProjectDetail(99)
            expect(store.currentProjectId).toBe(5)
        })
    })

    describe('resetState 保留全局上下文', () => {
        it('resetState 清空详情数据但保留 currentProjectId', () => {
            store.setCurrentProject(5)
            store.currentProject = makeProject({ id: 5, name: '项目E' })
            store.projectFiles = [
                { id: 1, project_id: 5, file_name: 'f', file_type: 'doc', file_url: '', file_source: 'file', size: 1, upload_time: '' },
            ]
            store.resetState()
            // 全局上下文保留：其他页面仍可继承
            expect(store.currentProjectId).toBe(5)
            // 详情级数据清空
            expect(store.currentProject).toBeNull()
            expect(store.projectFiles).toEqual([])
        })
    })

    describe('resolveInitialProjectId - URL 参数优先级', () => {
        it('URL 参数优先于 store 现有值', () => {
            expect(resolveInitialProjectId('10', 5)).toBe(10)
        })

        it('URL 参数与 store 值相同时返回该值', () => {
            expect(resolveInitialProjectId('7', 7)).toBe(7)
        })

        it('无 URL 参数时回退到 store 值', () => {
            expect(resolveInitialProjectId(undefined, 5)).toBe(5)
        })

        it('URL 为 null 时回退到 store 值', () => {
            expect(resolveInitialProjectId(null, 5)).toBe(5)
        })

        it('URL 为空字符串时回退到 store 值', () => {
            expect(resolveInitialProjectId('', 8)).toBe(8)
        })

        it('URL 非法时回退到 store 值', () => {
            expect(resolveInitialProjectId('abc', 8)).toBe(8)
        })

        it('URL 非法且 store 也为 null 时返回 0', () => {
            expect(resolveInitialProjectId('abc', null)).toBe(0)
        })

        it('URL 与 store 均无有效值时返回 0', () => {
            expect(resolveInitialProjectId(undefined, null)).toBe(0)
        })

        it('URL 为 0 或负数时视为无效，回退到 store', () => {
            expect(resolveInitialProjectId('0', 3)).toBe(3)
            expect(resolveInitialProjectId('-1', 3)).toBe(3)
        })
    })
})
