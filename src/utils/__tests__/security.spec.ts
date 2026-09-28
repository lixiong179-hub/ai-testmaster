import { describe, expect, it } from 'vitest'
import {
  sanitizeRedirect,
  validateUploadFile,
  MAX_UPLOAD_FILE_SIZE,
  ALLOWED_UPLOAD_EXTENSIONS,
} from '../security'

describe('sanitizeRedirect - 开放重定向防护', () => {
  it('合法站内路径原样返回', () => {
    expect(sanitizeRedirect('/home/workbench')).toBe('/home/workbench')
    expect(sanitizeRedirect('/home/case/detail/1')).toBe('/home/case/detail/1')
    expect(sanitizeRedirect('/login')).toBe('/login')
  })

  it('空值或非字符串回退到默认首页', () => {
    expect(sanitizeRedirect(null)).toBe('/home/workbench')
    expect(sanitizeRedirect(undefined)).toBe('/home/workbench')
    expect(sanitizeRedirect('')).toBe('/home/workbench')
    expect(sanitizeRedirect(123)).toBe('/home/workbench')
    expect(sanitizeRedirect({})).toBe('/home/workbench')
  })

  it('拒绝协议相对 URL（//evil.com）防止开放重定向', () => {
    expect(sanitizeRedirect('//evil.com')).toBe('/home/workbench')
    expect(sanitizeRedirect('//attacker.com/path')).toBe('/home/workbench')
    expect(sanitizeRedirect('//127.0.0.1:8080')).toBe('/home/workbench')
  })

  it('拒绝反斜杠变体（/\\evil.com）防止绕过', () => {
    expect(sanitizeRedirect('/\\evil.com')).toBe('/home/workbench')
    expect(sanitizeRedirect('/\\\\evil.com')).toBe('/home/workbench')
  })

  it('拒绝绝对 URL（http/https/javascript）', () => {
    expect(sanitizeRedirect('https://evil.com')).toBe('/home/workbench')
    expect(sanitizeRedirect('http://evil.com')).toBe('/home/workbench')
    expect(sanitizeRedirect('javascript:alert(1)')).toBe('/home/workbench')
  })

  it('拒绝不以 / 开头的路径', () => {
    expect(sanitizeRedirect('home/workbench')).toBe('/home/workbench')
    expect(sanitizeRedirect('relative/path')).toBe('/home/workbench')
  })

  it('带 query 参数的合法路径原样返回', () => {
    expect(sanitizeRedirect('/home/case?project_id=1')).toBe('/home/case?project_id=1')
    expect(sanitizeRedirect('/home/iteration/list?page=2')).toBe('/home/iteration/list?page=2')
  })
})

describe('validateUploadFile - 文件上传安全校验', () => {
  /**
   * 创建指定名称和大小的模拟 File 对象。
   * validateUploadFile 仅访问 .name 和 .size，无需真实文件内容，
   * 因此用轻量 mock 避免在测试中分配 50MB 内存。
   */
  function makeFile(name: string, size: number): File {
    return { name, size } as unknown as File
  }

  it('合法文件返回 null（通过校验）', () => {
    expect(validateUploadFile(makeFile('doc.pdf', 1024))).toBeNull()
    expect(validateUploadFile(makeFile('image.png', 2048))).toBeNull()
    expect(validateUploadFile(makeFile('data.xlsx', 500))).toBeNull()
    expect(validateUploadFile(makeFile('readme.md', 100))).toBeNull()
    expect(validateUploadFile(makeFile('archive.zip', 4096))).toBeNull()
  })

  it('拒绝不在白名单的危险扩展名', () => {
    expect(validateUploadFile(makeFile('malware.exe', 1024))).toContain('不支持的文件类型')
    expect(validateUploadFile(makeFile('script.js', 1024))).toContain('不支持的文件类型')
    expect(validateUploadFile(makeFile('shell.sh', 1024))).toContain('不支持的文件类型')
    expect(validateUploadFile(makeFile('page.html', 1024))).toContain('不支持的文件类型')
    expect(validateUploadFile(makeFile('app.jsp', 1024))).toContain('不支持的文件类型')
    expect(validateUploadFile(makeFile('binary.dll', 1024))).toContain('不支持的文件类型')
  })

  it('拒绝无扩展名的文件', () => {
    const result = validateUploadFile(makeFile('noextension', 1024))
    expect(result).toContain('不支持的文件类型')
  })

  it('拒绝超过大小限制的文件（DoS 防护）', () => {
    const oversized = makeFile('big.pdf', MAX_UPLOAD_FILE_SIZE + 1)
    const result = validateUploadFile(oversized)
    expect(result).toContain('超过 50MB 大小限制')
  })

  it('恰好等于大小限制的文件通过校验', () => {
    const exact = makeFile('exact.pdf', MAX_UPLOAD_FILE_SIZE)
    expect(validateUploadFile(exact)).toBeNull()
  })

  it('拒绝空文件（0 字节）', () => {
    const empty = makeFile('empty.txt', 0)
    const result = validateUploadFile(empty)
    expect(result).toContain('为空')
  })

  it('扩展名大小写不敏感（大写扩展名通过校验）', () => {
    expect(validateUploadFile(makeFile('IMAGE.PNG', 1024))).toBeNull()
    expect(validateUploadFile(makeFile('Doc.PDF', 1024))).toBeNull()
    expect(validateUploadFile(makeFile('DATA.XLSX', 1024))).toBeNull()
  })

  it('双扩展名文件取最后一个扩展名判断', () => {
    //恶意文件如 "file.exe.pdf" 应通过（后缀为 pdf）
    expect(validateUploadFile(makeFile('file.exe.pdf', 1024))).toBeNull()
    // "report.pdf.exe" 应被拒绝（后缀为 exe）
    expect(validateUploadFile(makeFile('report.pdf.exe', 1024))).toContain('不支持的文件类型')
  })

  it('白名单包含所有声明的扩展名', () => {
    const expected = [
      'txt',
      'doc',
      'docx',
      'pdf',
      'md',
      'xlsx',
      'xls',
      'csv',
      'json',
      'yaml',
      'yml',
      'png',
      'jpg',
      'jpeg',
      'gif',
      'webp',
      'bmp',
      'zip',
      'rar',
    ]
    for (const ext of expected) {
      expect(ALLOWED_UPLOAD_EXTENSIONS.has(ext)).toBe(true)
    }
  })

  it('白名单不包含危险扩展名', () => {
    const dangerous = ['exe', 'js', 'sh', 'bat', 'cmd', 'html', 'svg', 'xml', 'php', 'jsp', 'asp']
    for (const ext of dangerous) {
      expect(ALLOWED_UPLOAD_EXTENSIONS.has(ext)).toBe(false)
    }
  })
})
