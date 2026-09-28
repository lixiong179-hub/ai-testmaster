/**
 * useFileExtract 单元测试
 *
 * 覆盖范围：
 * 1. triggerAutoExtract：上传成功后自动触发提取（文档类过滤、空值、异常）
 * 2. handleRetryExtract：重试逻辑、计数器递增、上限阻断
 * 3. isRetryExhausted / getRetryCount：重试计数查询
 * 4. 轮询：syncPolling/startPolling/stopPolling 与 hasPendingFiles 判定
 */
import { describe, it, expect, beforeEach, vi, afterEach, type Mock } from 'vitest'
import { fileApi } from '@/api/file'
import { ElMessage } from 'element-plus'
import { useFileExtract } from '@/composables/requirement/useFileExtract'
import type { ExtractableResource } from '@/composables/requirement/useFileExtract'

vi.mock('@/api/file', () => ({
    fileApi: {
        extractContent: vi.fn(),
    },
}))

vi.mock('element-plus', () => ({
    ElMessage: {
        success: vi.fn(),
        error: vi.fn(),
        warning: vi.fn(),
        info: vi.fn(),
    },
}))

const messageSpy = vi.mocked(ElMessage)
const extractSpy = vi.mocked(fileApi.extractContent)

describe('useFileExtract', () => {
    let getResources: Mock<[], Promise<void>>
    let getProjectId: Mock<[], number>
    let getResourcesList: Mock<[], ExtractableResource[]>

    beforeEach(() => {
        vi.useFakeTimers()
        vi.clearAllMocks()
        getResources = vi.fn<[], Promise<void>>().mockResolvedValue(undefined)
        getProjectId = vi.fn<[], number>().mockReturnValue(1)
        getResourcesList = vi.fn<[], ExtractableResource[]>().mockReturnValue([])
    })

    afterEach(() => {
        vi.clearAllTimers()
        vi.useRealTimers()
    })

    /** 创建 composable 实例 */
    function createCtx() {
        return useFileExtract({ getResources, getProjectId, getResourcesList })
    }

    describe('triggerAutoExtract - 上传成功自动提取', () => {
        it('上传成功后自动对文档类文件触发 extract-content', async () => {
            extractSpy.mockResolvedValue({} as never)
            const ctx = createCtx()
            const response = {
                data: {
                    uploaded_files: [
                        { id: 101, resource_type: 'requirement' },
                        { id: 102, resource_type: 'api_doc' },
                    ],
                },
            }
            const count = await ctx.triggerAutoExtract(response)
            expect(extractSpy).toHaveBeenCalledTimes(1)
            expect(extractSpy).toHaveBeenCalledWith({
                file_ids: [101, 102],
                project_id: 1,
            })
            expect(count).toBe(2)
            expect(messageSpy.success).toHaveBeenCalledWith(
                '已自动触发 2 个文件的内容提取'
            )
        })

        it('跳过 ui_mockup 类型文件（仅提取文档类）', async () => {
            extractSpy.mockResolvedValue({} as never)
            const ctx = createCtx()
            const response = {
                data: {
                    uploaded_files: [
                        { id: 1, resource_type: 'ui_mockup' },
                        { id: 2, resource_type: 'requirement' },
                    ],
                },
            }
            const count = await ctx.triggerAutoExtract(response)
            expect(extractSpy).toHaveBeenCalledWith({
                file_ids: [2],
                project_id: 1,
            })
            expect(count).toBe(1)
        })

        it('无文档类文件时返回 0 且不调用提取接口', async () => {
            const ctx = createCtx()
            const response = {
                data: { uploaded_files: [{ id: 1, resource_type: 'ui_mockup' }] },
            }
            const count = await ctx.triggerAutoExtract(response)
            expect(extractSpy).not.toHaveBeenCalled()
            expect(count).toBe(0)
        })

        it('response 为空时返回 0', async () => {
            const ctx = createCtx()
            expect(await ctx.triggerAutoExtract(undefined)).toBe(0)
            expect(await ctx.triggerAutoExtract({})).toBe(0)
            expect(await ctx.triggerAutoExtract({ data: {} })).toBe(0)
            expect(extractSpy).not.toHaveBeenCalled()
        })

        it('uploaded_files 为空数组时返回 0', async () => {
            const ctx = createCtx()
            const count = await ctx.triggerAutoExtract({ data: { uploaded_files: [] } })
            expect(count).toBe(0)
            expect(extractSpy).not.toHaveBeenCalled()
        })

        it('无 project_id 时不触发提取', async () => {
            getProjectId.mockReturnValue(0)
            const ctx = createCtx()
            const count = await ctx.triggerAutoExtract({
                data: { uploaded_files: [{ id: 1, resource_type: 'requirement' }] },
            })
            expect(count).toBe(0)
            expect(extractSpy).not.toHaveBeenCalled()
        })

        it('提取接口异常时返回 0 并给出警告提示', async () => {
            extractSpy.mockRejectedValueOnce(new Error('network error'))
            const ctx = createCtx()
            const count = await ctx.triggerAutoExtract({
                data: { uploaded_files: [{ id: 1, resource_type: 'requirement' }] },
            })
            expect(count).toBe(0)
            expect(messageSpy.warning).toHaveBeenCalledWith(
                '部分文件内容提取触发失败，可在列表中手动重试'
            )
        })

        it('兼容 uploaded_files 直接挂在顶层的响应格式', async () => {
            extractSpy.mockResolvedValue({} as never)
            const ctx = createCtx()
            const response = {
                uploaded_files: [{ id: 9, resource_type: 'requirement' }],
            }
            const count = await ctx.triggerAutoExtract(response)
            expect(extractSpy).toHaveBeenCalledWith({
                file_ids: [9],
                project_id: 1,
            })
            expect(count).toBe(1)
        })
    })

    describe('handleRetryExtract - 重试提取逻辑', () => {
        it('以 force_refresh=true 重试单个文件', async () => {
            extractSpy.mockResolvedValue({} as never)
            const ctx = createCtx()
            await ctx.handleRetryExtract(501)
            expect(extractSpy).toHaveBeenCalledWith({
                file_ids: [501],
                project_id: 1,
                force_refresh: true,
            })
            expect(ctx.getRetryCount(501)).toBe(1)
        })

        it('每次重试递增计数器', async () => {
            extractSpy.mockResolvedValue({} as never)
            const ctx = createCtx()
            await ctx.handleRetryExtract(1)
            await ctx.handleRetryExtract(1)
            await ctx.handleRetryExtract(1)
            expect(ctx.getRetryCount(1)).toBe(3)
            expect(ctx.isRetryExhausted(1)).toBe(true)
        })

        it('达到上限（3次）后拒绝继续重试', async () => {
            extractSpy.mockResolvedValue({} as never)
            const ctx = createCtx()
            await ctx.handleRetryExtract(1)
            await ctx.handleRetryExtract(1)
            await ctx.handleRetryExtract(1)
            extractSpy.mockClear()
            await ctx.handleRetryExtract(1)
            expect(extractSpy).not.toHaveBeenCalled()
            expect(messageSpy.warning).toHaveBeenCalledWith(
                '重试次数已达上限，请联系管理员'
            )
        })

        it('API 失败时仍递增计数器', async () => {
            extractSpy.mockRejectedValue(new Error('fail'))
            const ctx = createCtx()
            await ctx.handleRetryExtract(1)
            expect(ctx.getRetryCount(1)).toBe(1)
        })

        it('第3次重试失败时提示联系管理员', async () => {
            extractSpy.mockRejectedValue(new Error('fail'))
            const ctx = createCtx()
            await ctx.handleRetryExtract(1)
            await ctx.handleRetryExtract(1)
            await ctx.handleRetryExtract(1)
            expect(messageSpy.error).toHaveBeenCalledWith(
                '重试次数已达上限（3次），请联系管理员处理'
            )
        })

        it('未达上限时重试失败提示普通错误', async () => {
            extractSpy.mockRejectedValueOnce(new Error('fail'))
            const ctx = createCtx()
            await ctx.handleRetryExtract(1)
            expect(messageSpy.error).toHaveBeenCalledWith('触发内容提取失败')
        })

        it('无 project_id 时不执行任何操作', async () => {
            getProjectId.mockReturnValue(0)
            const ctx = createCtx()
            await ctx.handleRetryExtract(1)
            expect(extractSpy).not.toHaveBeenCalled()
            expect(ctx.getRetryCount(1)).toBe(0)
        })

        it('fileId 为 0 时不执行任何操作', async () => {
            const ctx = createCtx()
            await ctx.handleRetryExtract(0)
            expect(extractSpy).not.toHaveBeenCalled()
        })

        it('重试成功后刷新资源列表', async () => {
            extractSpy.mockResolvedValue({} as never)
            const ctx = createCtx()
            await ctx.handleRetryExtract(1)
            expect(getResources).toHaveBeenCalledTimes(1)
        })
    })

    describe('isRetryExhausted / getRetryCount - 计数查询', () => {
        it('初始状态计数为 0 且未耗尽', () => {
            const ctx = createCtx()
            expect(ctx.getRetryCount(999)).toBe(0)
            expect(ctx.isRetryExhausted(999)).toBe(false)
        })

        it('不同文件计数互不影响', async () => {
            extractSpy.mockResolvedValue({} as never)
            const ctx = createCtx()
            await ctx.handleRetryExtract(1)
            await ctx.handleRetryExtract(1)
            expect(ctx.getRetryCount(2)).toBe(0)
            expect(ctx.isRetryExhausted(2)).toBe(false)
            expect(ctx.isRetryExhausted(1)).toBe(false)
        })
    })

    describe('轮询 - 实时状态更新', () => {
        it('存在 processing 文件时轮询刷新资源列表', async () => {
            extractSpy.mockResolvedValue({} as never)
            getResourcesList.mockReturnValue([
                { id: 1, resource_type: 'requirement', extract_status: 'processing' },
            ])
            const ctx = createCtx()
            ctx.startPolling()
            await vi.advanceTimersByTimeAsync(3000)
            expect(getResources).toHaveBeenCalledTimes(1)
            await vi.advanceTimersByTimeAsync(3000)
            expect(getResources).toHaveBeenCalledTimes(2)
        })

        it('存在 pending 文件时也启动轮询', async () => {
            getResourcesList.mockReturnValue([
                { id: 1, resource_type: 'requirement', extract_status: 'pending' },
            ])
            const ctx = createCtx()
            ctx.startPolling()
            await vi.advanceTimersByTimeAsync(3000)
            expect(getResources).toHaveBeenCalledTimes(1)
        })

        it('所有文件达终态后自动停止轮询', async () => {
            getResourcesList.mockReturnValue([
                { id: 1, resource_type: 'requirement', extract_status: 'completed' },
                { id: 2, resource_type: 'api_doc', extract_status: 'failed' },
            ])
            const ctx = createCtx()
            ctx.startPolling()
            // 第一次 tick：hasPendingFiles=false → 停止轮询，不调用 getResources
            await vi.advanceTimersByTimeAsync(3000)
            expect(getResources).not.toHaveBeenCalled()
            // 轮询已停止，再推进时间也不触发
            await vi.advanceTimersByTimeAsync(6000)
            expect(getResources).not.toHaveBeenCalled()
        })

        it('ui_mockup 文件不计入待轮询判定', async () => {
            getResourcesList.mockReturnValue([
                { id: 1, resource_type: 'ui_mockup', extract_status: 'processing' },
            ])
            const ctx = createCtx()
            ctx.startPolling()
            await vi.advanceTimersByTimeAsync(3000)
            // ui_mockup processing 不触发轮询刷新
            expect(getResources).not.toHaveBeenCalled()
        })

        it('syncPolling 在有 pending 文件时启动轮询', async () => {
            getResourcesList.mockReturnValue([
                { id: 1, resource_type: 'requirement', extract_status: 'processing' },
            ])
            const ctx = createCtx()
            ctx.syncPolling()
            await vi.advanceTimersByTimeAsync(3000)
            expect(getResources).toHaveBeenCalledTimes(1)
        })

        it('syncPolling 在无 pending 文件时停止轮询', async () => {
            getResourcesList.mockReturnValue([
                { id: 1, resource_type: 'requirement', extract_status: 'completed' },
            ])
            const ctx = createCtx()
            ctx.syncPolling()
            await vi.advanceTimersByTimeAsync(3000)
            expect(getResources).not.toHaveBeenCalled()
        })

        it('stopPolling 后不再刷新列表', async () => {
            getResourcesList.mockReturnValue([
                { id: 1, resource_type: 'requirement', extract_status: 'processing' },
            ])
            const ctx = createCtx()
            ctx.startPolling()
            ctx.stopPolling()
            await vi.advanceTimersByTimeAsync(6000)
            expect(getResources).not.toHaveBeenCalled()
        })

        it('重复调用 startPolling 不会创建多个定时器', async () => {
            getResourcesList.mockReturnValue([
                { id: 1, resource_type: 'requirement', extract_status: 'processing' },
            ])
            const ctx = createCtx()
            ctx.startPolling()
            ctx.startPolling()
            ctx.startPolling()
            await vi.advanceTimersByTimeAsync(3000)
            expect(getResources).toHaveBeenCalledTimes(1)
        })

        it('extract_status 为 undefined 时按 pending 处理（触发轮询）', async () => {
            const list: ExtractableResource[] = [
                { id: 1, resource_type: 'requirement' },
            ]
            getResourcesList.mockReturnValue(list)
            const ctx = createCtx()
            ctx.syncPolling()
            await vi.advanceTimersByTimeAsync(3000)
            expect(getResources).toHaveBeenCalledTimes(1)
        })

        it('空列表不触发轮询', async () => {
            getResourcesList.mockReturnValue([])
            const ctx = createCtx()
            ctx.syncPolling()
            await vi.advanceTimersByTimeAsync(6000)
            expect(getResources).not.toHaveBeenCalled()
        })

        it('triggerAutoExtract 成功后启动轮询', async () => {
            extractSpy.mockResolvedValue({} as never)
            getResourcesList.mockReturnValue([
                { id: 101, resource_type: 'requirement', extract_status: 'pending' },
            ])
            const ctx = createCtx()
            await ctx.triggerAutoExtract({
                data: { uploaded_files: [{ id: 101, resource_type: 'requirement' }] },
            })
            // 轮询已启动，3秒后应刷新
            await vi.advanceTimersByTimeAsync(3000)
            expect(getResources).toHaveBeenCalled()
        })

        it('handleRetryExtract 成功后启动轮询', async () => {
            extractSpy.mockResolvedValue({} as never)
            getResourcesList.mockReturnValue([
                { id: 1, resource_type: 'requirement', extract_status: 'processing' },
            ])
            const ctx = createCtx()
            await ctx.handleRetryExtract(1)
            getResources.mockClear()
            await vi.advanceTimersByTimeAsync(3000)
            expect(getResources).toHaveBeenCalled()
        })
    })
})
