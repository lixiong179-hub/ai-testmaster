import { describe, it, expect, beforeEach, vi } from 'vitest'

const { mockRequest } = vi.hoisted(() => ({
  mockRequest: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('@/utils/request', () => ({
  default: mockRequest,
}))

import { fileApi, FileAPI } from '@/api/file'

function makeFile(name = 'a.txt'): File {
  return new File(['content'], name, { type: 'text/plain' })
}

describe('fileApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRequest.get.mockResolvedValue({ code: 200, data: {} })
    mockRequest.post.mockResolvedValue({ code: 200, data: {} })
    mockRequest.put.mockResolvedValue({ code: 200, data: {} })
    mockRequest.delete.mockResolvedValue({ code: 200, data: {} })
  })

  it('默认导出与 FileAPI 别名指向同一对象（向后兼容）', () => {
    expect(FileAPI).toBe(fileApi)
  })

  it('uploadFile: multipart 字段含 project_id/file/resource_type/description', async () => {
    await fileApi.uploadFile(10, makeFile(), 'requirement', '需求文档')

    expect(mockRequest.post).toHaveBeenCalledTimes(1)
    const [url, body] = mockRequest.post.mock.calls[0] as [string, FormData]
    expect(url).toBe('/api/v1/file/upload')
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('project_id')).toBe('10')
    expect(body.get('resource_type')).toBe('requirement')
    expect(body.get('description')).toBe('需求文档')
    expect(body.get('file')).toBeInstanceOf(File)
    expect(body.get('iteration_id')).toBeNull()
  })

  it('uploadFile: 传 iterationId 时补 iteration_id 字段', async () => {
    await fileApi.uploadFile(10, makeFile(), 'other', '', 88)

    const [, body] = mockRequest.post.mock.calls[0] as [string, FormData]
    expect(body.get('iteration_id')).toBe('88')
  })

  it('submitUrl: POST /api/v1/file/submit-url 且原样透传 body', async () => {
    const payload = { project_id: 10, url: 'https://x.test', file_type: 'url' }

    await fileApi.submitUrl(payload)

    expect(mockRequest.post).toHaveBeenCalledWith('/api/v1/file/submit-url', payload)
  })

  it('getAllFiles: 无 iterationId 时 params 为空对象', async () => {
    await fileApi.getAllFiles()

    expect(mockRequest.get).toHaveBeenCalledWith('/api/v1/file/list', { params: {} })
  })

  it('getAllFiles: 传 iterationId 时带上 iteration_id', async () => {
    await fileApi.getAllFiles(5)

    expect(mockRequest.get).toHaveBeenCalledWith('/api/v1/file/list', {
      params: { iteration_id: 5 },
    })
  })

  it('getPreviewScreen: 走 blob 响应，避免预览被 JSON 解析', async () => {
    await fileApi.getPreviewScreen(3)

    expect(mockRequest.get).toHaveBeenCalledWith('/api/v1/file/preview-screen/3', {
      responseType: 'blob',
    })
  })

  it('getFileList: 默认分页 page=1/page_size=100，可显式指定', async () => {
    await fileApi.getFileList(10)
    await fileApi.getFileList(10, 5, 2, 20)

    expect(mockRequest.get).toHaveBeenNthCalledWith(1, '/api/v1/file/list/10', {
      params: { page: 1, page_size: 100 },
    })
    expect(mockRequest.get).toHaveBeenNthCalledWith(2, '/api/v1/file/list/10', {
      params: { page: 2, page_size: 20, iteration_id: 5 },
    })
  })

  it('extractContent: 透传 force_refresh 以支持强制重解析', async () => {
    const payload = { file_ids: [1, 2], project_id: 10, force_refresh: true }

    await fileApi.extractContent(payload)

    expect(mockRequest.post).toHaveBeenCalledWith('/api/v1/file/extract-content', payload)
  })

  it('batchUploadFiles: files 逐项 append 到同名 files 字段', async () => {
    await fileApi.batchUploadFiles(
      10,
      [makeFile('a.png'), makeFile('b.png')],
      'ui_mockup',
      '原型',
      '批次1',
      7
    )

    const [url, body] = mockRequest.post.mock.calls[0] as [string, FormData]
    expect(url).toBe('/api/v1/file/batch-upload')
    expect(body.getAll('files')).toHaveLength(2)
    expect(body.get('project_id')).toBe('10')
    expect(body.get('resource_type')).toBe('ui_mockup')
    expect(body.get('name')).toBe('批次1')
    expect(body.get('iteration_id')).toBe('7')
  })

  it('batchUploadFiles: name 为空时不提交该字段', async () => {
    await fileApi.batchUploadFiles(10, [makeFile()], 'ui_mockup', '')

    const [, body] = mockRequest.post.mock.calls[0] as [string, FormData]
    expect(body.get('name')).toBeNull()
  })

  it('updateFile / deleteFile: 路径含 fileId，删除携带 project_id 归属校验', async () => {
    await fileApi.updateFile(3, { resource_type: 'api_doc' })
    await fileApi.deleteFile(3, 10)

    expect(mockRequest.put).toHaveBeenCalledWith('/api/v1/file/3', { resource_type: 'api_doc' })
    expect(mockRequest.delete).toHaveBeenCalledWith('/api/v1/file/3', {
      params: { project_id: 10 },
    })
  })
})
