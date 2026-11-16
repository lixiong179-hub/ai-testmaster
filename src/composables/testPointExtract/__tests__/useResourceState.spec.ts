import { describe, it, expect, vi, beforeEach } from 'vitest'
import { silenceConsole } from '@/test-utils'
import type { ExtractSharedState, FileItem } from '../types'

const mocks = vi.hoisted(() => ({
  getProjects: vi.fn(),
  getFileListByProject: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ query: {} }),
}))

vi.mock('@/api/project', () => ({
  default: { getProjects: mocks.getProjects },
}))

vi.mock('@/api/file', () => ({
  fileApi: { getFileListByProject: mocks.getFileListByProject },
}))

import { createSharedState } from '../createSharedState'
import { useResourceState } from '../useResourceState'

let state: ExtractSharedState
let resource: ReturnType<typeof useResourceState>

function makeFile(overrides: Partial<FileItem> = {}): FileItem {
  return {
    id: 1,
    project_id: 9,
    file_name: '需求.docx',
    file_url: '/files/1',
    file_type: 'docx',
    size: 2048,
    upload_time: '2026-06-27 10:00:00',
    file_source: 'local',
    resource_type: 'requirement',
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceConsole()
  state = createSharedState()
  resource = useResourceState(state)
})

describe('useResourceState — 项目与资源计算属性', () => {
  it('未选项目时项目信息为空、projectId 为 0', () => {
    expect(resource.selectedProjectInfo.value).toBeNull()
    expect(resource.currentProjectId.value).toBe(0)
  })

  it('按 formData.project_id 取项目信息，找不到时为空', () => {
    state.projects.value = [{ id: 9, name: '项目A' }]
    state.formData.project_id = 9

    expect(resource.selectedProjectInfo.value).toEqual({ id: 9, name: '项目A' })

    state.formData.project_id = 404
    expect(resource.selectedProjectInfo.value).toBeNull()
  })

  it('把文件列表映射为资源行', () => {
    state.files.value = [makeFile()]

    expect(resource.resourceRows.value).toEqual([
      {
        source: 'file',
        id: 1,
        project_id: 9,
        display_name: '需求.docx',
        resource_type: 'requirement',
        type_label: '需求文档',
        size_text: '2.00 KB',
        time_text: '2026-06-27 10:00:00',
      },
    ])
  })

  it('资源缺少类型时回退为 other', () => {
    state.files.value = [makeFile({ resource_type: undefined })]

    expect(resource.resourceRows.value[0].resource_type).toBe('other')
    expect(resource.resourceRows.value[0].type_label).toBe('其他')
  })

  it('按资源类型过滤，未设置过滤时返回全部', () => {
    state.files.value = [
      makeFile({ id: 1, resource_type: 'requirement' }),
      makeFile({ id: 2, resource_type: 'api_doc' }),
    ]

    expect(resource.filteredResourceRows.value).toHaveLength(2)

    state.resourceTypeFilter.value = 'api_doc'
    expect(resource.filteredResourceRows.value.map((r) => r.id)).toEqual([2])
  })
})

describe('useResourceState — 展示格式化', () => {
  it.each([
    [512, '512 B'],
    [2048, '2.00 KB'],
    [5 * 1024 * 1024, '5.00 MB'],
  ])('文件大小 %s 展示为 %s', (size, expected) => {
    expect(resource.formatFileSize(size)).toBe(expected)
  })

  it.each([
    ['requirement', '需求文档', 'primary', 'Document'],
    ['ui_mockup', 'UI原型图', 'warning', 'Picture'],
    ['api_doc', 'API文档', 'success', 'DocumentCopy'],
    ['test_data', '测试数据', 'info', 'Files'],
    ['other', '其他', 'info', 'Document'],
  ])('资源类型 %s 的标签/颜色/图标', (type, label, tagType, icon) => {
    expect(resource.getResourceTypeLabel(type)).toBe(label)
    expect(resource.getResourceTypeTagType(type)).toBe(tagType)
    expect(resource.getResourceIcon(type)).toBe(icon)
  })

  it('未知类型原样展示标签并回退 info 与 Document 图标', () => {
    expect(resource.getResourceTypeLabel('custom')).toBe('custom')
    expect(resource.getResourceTypeTagType('custom')).toBe('info')
    expect(resource.getResourceIcon('custom')).toBe('Document')
  })

  it('统计类型数量与占比', () => {
    state.files.value = [
      makeFile({ id: 1, resource_type: 'requirement' }),
      makeFile({ id: 2, resource_type: 'requirement' }),
      makeFile({ id: 3, resource_type: 'api_doc' }),
    ]

    expect(resource.getResourceTypeCount('requirement')).toBe(2)
    expect(resource.getResourceTypePercentage('requirement')).toBe(67)
    expect(resource.getResourceTypePercentage('test_data')).toBe(0)
  })

  it('资源为空时占比为 0', () => {
    expect(resource.getResourceTypePercentage('requirement')).toBe(0)
  })
})

describe('useResourceState — 数据加载', () => {
  it('拉取项目列表时过滤「默认项目」', async () => {
    mocks.getProjects.mockResolvedValue({
      data: {
        items: [
          { id: 9, name: '项目A' },
          { id: 10, name: '默认项目' },
        ],
      },
    })

    await resource.getProjects()

    expect(mocks.getProjects).toHaveBeenCalledWith({})
    expect(state.projects.value).toEqual([{ id: 9, name: '项目A' }])
  })

  it('项目接口返回结构异常时置为空数组', async () => {
    mocks.getProjects.mockResolvedValue({})

    await resource.getProjects()

    expect(state.projects.value).toEqual([])
  })

  it('项目接口异常时降级为空数组且不抛出', async () => {
    mocks.getProjects.mockRejectedValue(new Error('boom'))

    await expect(resource.getProjects()).resolves.toBeUndefined()
    expect(state.projects.value).toEqual([])
  })

  it('按项目拉取文件列表', async () => {
    mocks.getFileListByProject.mockResolvedValue({ data: { items: [makeFile()] } })

    await resource.loadResources(9)

    expect(mocks.getFileListByProject).toHaveBeenCalledWith(9)
    expect(state.files.value).toHaveLength(1)
  })

  it('文件接口返回结构异常或异常时置为空数组', async () => {
    mocks.getFileListByProject.mockResolvedValueOnce({ data: {} })
    await resource.loadResources(9)
    expect(state.files.value).toEqual([])

    mocks.getFileListByProject.mockRejectedValueOnce(new Error('boom'))
    await resource.loadResources(9)
    expect(state.files.value).toEqual([])
  })

  it('handleResourceSelect 记录选中的资源行', () => {
    state.files.value = [makeFile()]

    resource.handleResourceSelect(resource.resourceRows.value[0])

    expect(state.selectedResource.value?.id).toBe(1)
  })
})
