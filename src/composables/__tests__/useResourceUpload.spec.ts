import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ElMessage } from 'element-plus'

const mocks = vi.hoisted(() => ({
  uploadFile: vi.fn(),
  updateFile: vi.fn(),
  uploadUIScreens: vi.fn(),
}))

vi.mock('@/api/file', () => {
  const api = { uploadFile: mocks.uploadFile, updateFile: mocks.updateFile }
  return { fileApi: api, default: api }
})

vi.mock('@/api/uiPrototype', () => {
  const api = { uploadUIScreens: mocks.uploadUIScreens }
  return { uiPrototypeApi: api, default: api }
})

import { createFormInstanceMock, silenceElMessage } from '@/test-utils'
import { useResourceUpload } from '../useResourceUpload'
import { RESOURCE_CONFIG } from '@/constants/resource'

function makeManager(overrides: Record<string, unknown> = {}) {
  return {
    iterations: [{ id: 1, name: '迭代A' }],
    selectedIterationId: null as number | null,
    getIterationNameById: vi.fn((id: number) => (id === 1 ? '迭代A' : '未分类')),
    showError: vi.fn(),
    ...overrides,
  } as never
}

function makeUploadFile(name: string, raw = new File(['x'], name)) {
  return { name, raw } as never
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mocks.uploadFile.mockResolvedValue({ code: 200 })
  mocks.updateFile.mockResolvedValue({ code: 200 })
  mocks.uploadUIScreens.mockResolvedValue({ data: { total: 3 } })
})

describe('useResourceUpload — 弹窗与表单', () => {
  it('初始状态与标题', () => {
    const upload = useResourceUpload(makeManager(), vi.fn())

    expect(upload.fileDialogVisible).toBe(false)
    expect(upload.fileDialogMode).toBe('add')
    expect(upload.fileDialogTitle).toBe('上传文件')
    expect(upload.isBatchUpload).toBe(false)
    expect(upload.fileFormData.project_id).toBe('')
    expect(upload.fileFormData.resource_type).toBe('requirement')
    expect(upload.fileFormRules.name[0].required).toBe(true)
  })

  it('新增时未选择迭代则迭代为空', () => {
    const upload = useResourceUpload(makeManager(), vi.fn())

    upload.handleAddFile()

    expect(upload.fileDialogVisible).toBe(true)
    expect(upload.fileFormData.iteration_id).toBeNull()
  })

  it('新增时选中具体迭代则带入迭代 ID', () => {
    const upload = useResourceUpload(makeManager({ selectedIterationId: 1 }), vi.fn())

    upload.handleAddFile()

    expect(upload.fileFormData.iteration_id).toBe(1)
  })

  it('新增时选中未分类则带入未分类标识', () => {
    const upload = useResourceUpload(makeManager({ selectedIterationId: 0 }), vi.fn())

    upload.handleAddFile()

    expect(upload.fileFormData.iteration_id).toBe(RESOURCE_CONFIG.ITERATION_UNCLASSIFIED)
  })

  it('迭代上下文缺失时不打开弹窗', () => {
    const upload = useResourceUpload(makeManager({ iterations: undefined }), vi.fn())

    upload.handleAddFile()

    expect(upload.fileDialogVisible).toBe(false)
  })

  it('编辑资源回填表单', () => {
    const upload = useResourceUpload(makeManager(), vi.fn())

    upload.handleEdit({
      id: 11,
      project_id: 7,
      name: '文档',
      resource_type: 'requirement',
      description: '说明',
      is_active: false,
      iteration_id: 1,
    } as never)

    expect(upload.fileDialogMode).toBe('edit')
    expect(upload.fileDialogTitle).toBe('编辑文件')
    expect(upload.fileFormData).toMatchObject({
      id: 11,
      project_id: 7,
      name: '文档',
      description: '说明',
      is_active: false,
      iteration_id: 1,
    })
    expect(upload.fileDialogVisible).toBe(true)
  })

  it('编辑未分类资源时回填未分类标识', () => {
    const upload = useResourceUpload(makeManager(), vi.fn())

    upload.handleEdit({
      id: 11,
      project_id: 7,
      name: '文档',
      resource_type: 'requirement',
      is_active: true,
      iteration_id: 0,
    } as never)

    expect(upload.fileFormData.iteration_id).toBe(RESOURCE_CONFIG.ITERATION_UNCLASSIFIED)
  })

  it('resetFileForm 恢复默认值', () => {
    const upload = useResourceUpload(makeManager(), vi.fn())
    upload.fileFormData.name = 'x'
    upload.fileFormData.iteration_id = 1
    upload.selectedFile = new File(['x'], 'a.txt')

    upload.resetFileForm()

    expect(upload.fileFormData.name).toBe('')
    expect(upload.fileFormData.iteration_id).toBeNull()
    expect(upload.selectedFile).toBeNull()
    expect(upload.selectedFiles).toEqual([])
  })
})

describe('useResourceUpload — 文件选择', () => {
  it('单文件选择自动用文件名作为资源名', () => {
    const upload = useResourceUpload(makeManager(), vi.fn())

    upload.handleFileChange(makeUploadFile('需求文档.pdf'), [makeUploadFile('需求文档.pdf')])

    expect(upload.fileFormData.name).toBe('需求文档')
    expect(upload.selectedFile).toBeInstanceOf(File)
    expect(upload.fileFormData.file).toBeInstanceOf(File)
  })

  it('已填写名称时不覆盖', () => {
    const upload = useResourceUpload(makeManager(), vi.fn())
    upload.fileFormData.name = '自定义'

    upload.handleFileChange(makeUploadFile('a.txt'), [])

    expect(upload.fileFormData.name).toBe('自定义')
  })

  it('批量上传模式收集全部文件', () => {
    const upload = useResourceUpload(makeManager(), vi.fn())
    upload.fileFormData.resource_type = 'ui_mockup'

    upload.handleFileChange(makeUploadFile('a.png'), [
      makeUploadFile('a.png'),
      makeUploadFile('b.png'),
    ])

    expect(upload.isBatchUpload).toBe(true)
    expect(upload.selectedFiles).toHaveLength(2)
    expect(upload.fileFormData.name).toBe('UI原型图批量上传')
  })

  it('移除文件按模式分别清理', () => {
    const upload = useResourceUpload(makeManager(), vi.fn())
    upload.handleFileChange(makeUploadFile('a.txt'), [makeUploadFile('a.txt')])

    upload.handleFileRemove(makeUploadFile('a.txt'), [])

    expect(upload.selectedFile).toBeNull()
    expect(upload.fileFormData.file).toBeNull()

    upload.fileFormData.resource_type = 'ui_mockup'
    upload.handleFileRemove(makeUploadFile('a.png'), [makeUploadFile('b.png')])

    expect(upload.selectedFiles).toHaveLength(1)
  })

  it('超限提示按模式区分文案', () => {
    const upload = useResourceUpload(makeManager(), vi.fn())

    upload.handleExceed()
    expect(ElMessage.warning).toHaveBeenCalledWith('只能上传1个文件')

    upload.fileFormData.resource_type = 'ui_mockup'
    upload.handleExceed()
    expect(ElMessage.warning).toHaveBeenCalledWith('最多上传20个文件')
  })

  it('迭代名称展示分三种情况', () => {
    const upload = useResourceUpload(makeManager(), vi.fn())

    upload.fileFormData.iteration_id = null
    expect(upload.getCurrentIterationName()).toBe('未选择')

    upload.fileFormData.iteration_id = RESOURCE_CONFIG.ITERATION_UNCLASSIFIED
    expect(upload.getCurrentIterationName()).toBe('未分类')

    upload.fileFormData.iteration_id = 1
    expect(upload.getCurrentIterationName()).toBe('迭代A')
  })
})

describe('useResourceUpload — 提交', () => {
  it('表单实例缺失时提示刷新', async () => {
    const upload = useResourceUpload(makeManager(), vi.fn())

    await upload.handleFileSubmit()

    expect(ElMessage.error).toHaveBeenCalledWith('表单初始化失败，请刷新页面重试')
    expect(mocks.uploadFile).not.toHaveBeenCalled()
  })

  it('校验不通过时中断', async () => {
    const refresh = vi.fn()
    const upload = useResourceUpload(makeManager(), refresh)
    const form = createFormInstanceMock({ valid: false })

    await upload.handleFileSubmit(form as never)

    expect(form.validate).toHaveBeenCalled()
    expect(mocks.uploadFile).not.toHaveBeenCalled()
    expect(refresh).not.toHaveBeenCalled()
  })

  it('编辑模式调用更新接口', async () => {
    const refresh = vi.fn()
    const upload = useResourceUpload(makeManager(), refresh)
    upload.handleEdit({
      id: 11,
      project_id: 7,
      name: '文档',
      resource_type: 'requirement',
      is_active: true,
      iteration_id: 1,
    } as never)
    upload.fileFormData.description = '新说明'

    await upload.handleFileSubmit(createFormInstanceMock() as never)

    expect(mocks.updateFile).toHaveBeenCalledWith(11, {
      resource_type: 'requirement',
      description: '新说明',
      iteration_id: 1,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('文件信息更新成功')
    expect(upload.fileDialogVisible).toBe(false)
    expect(refresh).toHaveBeenCalled()
    expect(upload.submitting).toBe(false)
  })

  it('编辑模式未分类时迭代参数为 null', async () => {
    const upload = useResourceUpload(makeManager(), vi.fn())
    upload.handleEdit({
      id: 11,
      project_id: 7,
      name: '文档',
      resource_type: 'requirement',
      is_active: true,
      iteration_id: 0,
    } as never)

    await upload.handleFileSubmit(createFormInstanceMock() as never)

    expect(mocks.updateFile).toHaveBeenCalledWith(
      11,
      expect.objectContaining({ iteration_id: null })
    )
  })

  it('批量上传未选文件时提示', async () => {
    const upload = useResourceUpload(makeManager(), vi.fn())
    upload.fileFormData.resource_type = 'ui_mockup'
    upload.fileFormData.project_id = 7

    await upload.handleFileSubmit(createFormInstanceMock() as never)

    expect(ElMessage.warning).toHaveBeenCalledWith('请选择文件')
    expect(mocks.uploadUIScreens).not.toHaveBeenCalled()
  })

  it('批量上传成功提示数量与迭代名', async () => {
    const refresh = vi.fn()
    const upload = useResourceUpload(makeManager(), refresh)
    upload.fileFormData.resource_type = 'ui_mockup'
    upload.fileFormData.project_id = 7
    upload.fileFormData.name = '原型'
    upload.fileFormData.iteration_id = 1
    upload.selectedFiles = [new File(['a'], 'a.png')]

    await upload.handleFileSubmit(createFormInstanceMock() as never)

    expect(mocks.uploadUIScreens).toHaveBeenCalledWith(7, expect.any(Array), '原型', undefined, 1)
    expect(ElMessage.success).toHaveBeenCalledWith('成功上传 3 张UI原型图到迭代 "迭代A"')
    expect(refresh).toHaveBeenCalled()
  })

  it('批量上传未创建记录时给出警告', async () => {
    mocks.uploadUIScreens.mockResolvedValue({ data: { total: 0 } })
    const upload = useResourceUpload(makeManager(), vi.fn())
    upload.fileFormData.resource_type = 'ui_mockup'
    upload.fileFormData.project_id = 7
    upload.selectedFiles = [new File(['a'], 'a.png')]

    await upload.handleFileSubmit(createFormInstanceMock() as never)

    expect(ElMessage.warning).toHaveBeenCalledWith('上传完成，但未成功创建任何屏幕记录')
  })

  it('批量上传名称为空时使用默认名称', async () => {
    const upload = useResourceUpload(makeManager(), vi.fn())
    upload.fileFormData.resource_type = 'ui_mockup'
    upload.fileFormData.project_id = 7
    upload.selectedFiles = [new File(['a'], 'a.png')]

    await upload.handleFileSubmit(createFormInstanceMock() as never)

    expect(mocks.uploadUIScreens).toHaveBeenCalledWith(
      7,
      expect.any(Array),
      'UI原型图',
      undefined,
      undefined
    )
  })

  it('单文件上传未选文件时提示', async () => {
    const upload = useResourceUpload(makeManager(), vi.fn())
    upload.fileFormData.project_id = 7

    await upload.handleFileSubmit(createFormInstanceMock() as never)

    expect(ElMessage.warning).toHaveBeenCalledWith('请选择文件')
    expect(mocks.uploadFile).not.toHaveBeenCalled()
  })

  it('单文件上传成功提示文件名', async () => {
    const refresh = vi.fn()
    const upload = useResourceUpload(makeManager(), refresh)
    upload.fileFormData.project_id = 7
    upload.fileFormData.name = '需求文档'
    upload.fileFormData.description = ''
    upload.selectedFile = new File(['a'], 'a.txt')

    await upload.handleFileSubmit(createFormInstanceMock() as never)

    expect(mocks.uploadFile).toHaveBeenCalledWith(7, expect.any(File), 'requirement', '', undefined)
    expect(ElMessage.success).toHaveBeenCalledWith('文件 "需求文档" 上传成功')
    expect(refresh).toHaveBeenCalled()
    expect(upload.fileDialogVisible).toBe(false)
  })

  it('上传异常交由迭代管理器的 showError 处理', async () => {
    mocks.uploadFile.mockRejectedValue(new Error('boom'))
    const manager = makeManager()
    const upload = useResourceUpload(manager, vi.fn())
    upload.fileFormData.project_id = 7
    upload.selectedFile = new File(['a'], 'a.txt')

    await upload.handleFileSubmit(createFormInstanceMock() as never)

    expect((manager as { showError: unknown }).showError).toHaveBeenCalledWith(
      '上传文件',
      expect.any(Error)
    )
    expect(upload.submitting).toBe(false)
  })
})
