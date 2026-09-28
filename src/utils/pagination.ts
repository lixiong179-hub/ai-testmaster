/**
 * 从后端分页响应中提取列表数据
 * 支持 { data: [...] } 和 { items: [...] } 两种结构
 */
export function extractListData(resp: unknown): unknown[] {
  const data = (resp as { data?: unknown })?.data || resp
  return Array.isArray(data) ? data : (data as { items?: unknown[] })?.items || []
}
