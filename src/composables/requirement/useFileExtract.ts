/**
 * 文件内容提取 Composable
 * 职责：
 * 1. 上传成功后自动触发内容提取（后台异步，仅文档类资源）
 * 2. 维护每文件重试计数器（上限 MAX_RETRY_COUNT 次，超出后隐藏重试入口）
 * 3. 轮询提取状态（pending/processing 时每 POLL_INTERVAL 毫秒刷新，终态自动停止）
 *
 * 设计说明：后端暂无文件提取专用 WebSocket 通道，故采用轮询方案；
 * 若后续后端提供 WS 推送，可在此处优先连接 WS 并降级轮询。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fileApi, type FileBatchUploadResponse } from '@/api/file'

/** 单文件最大重试次数 */
const MAX_RETRY_COUNT = 3
/** 状态轮询间隔（毫秒） */
const POLL_INTERVAL = 3000
/** 提取终态：收到后停止轮询 */
const TERMINAL_STATUSES = new Set(['completed', 'failed'])

/** 可提取的资源行最小结构（避免与完整 Resource 耦合） */
export interface ExtractableResource {
    id: number
    resource_type: string
    extract_status?: string
}

/** 上传成功响应中 uploaded_files 项的结构 */
interface UploadedFileItem {
    id: number
    resource_type?: string
}

export interface UseFileExtractOptions {
    /** 刷新资源列表 */
    getResources: () => Promise<void> | void
    /** 获取当前项目 ID */
    getProjectId: () => number
    /** 获取当前资源列表（用于判断是否存在待轮询文件） */
    getResourcesList: () => ExtractableResource[]
}

export function useFileExtract(options: UseFileExtractOptions) {
    const { getResources, getProjectId, getResourcesList } = options

    /** 重试计数器：fileId -> 已重试次数 */
    const retryCountMap = ref<Record<number, number>>({})
    /** 轮询定时器 */
    let pollTimer: ReturnType<typeof setInterval> | null = null

    /** 获取指定文件的重试次数 */
    const getRetryCount = (fileId: number): number => retryCountMap.value[fileId] ?? 0

    /** 重试次数是否已达上限 */
    const isRetryExhausted = (fileId: number): boolean =>
        getRetryCount(fileId) >= MAX_RETRY_COUNT

    /** 是否存在待轮询的文件（pending/processing 的文档类资源） */
    const hasPendingFiles = (): boolean =>
        getResourcesList().some(
            (f) =>
                f.id &&
                f.resource_type !== 'ui_mockup' &&
                !TERMINAL_STATUSES.has(f.extract_status || 'pending')
        )

    /** 启动轮询：存在 pending/processing 文件时每 POLL_INTERVAL 毫秒刷新列表 */
    const startPolling = (): void => {
        if (pollTimer) return
        pollTimer = setInterval(async () => {
            if (!hasPendingFiles()) {
                stopPolling()
                return
            }
            await getResources()
        }, POLL_INTERVAL)
    }

    /** 停止轮询 */
    const stopPolling = (): void => {
        if (pollTimer) {
            clearInterval(pollTimer)
            pollTimer = null
        }
    }

    /** 根据当前列表同步轮询状态：有 pending 则启动，无则停止 */
    const syncPolling = (): void => {
        if (hasPendingFiles()) {
            startPolling()
        } else {
            stopPolling()
        }
    }

    /**
     * 上传成功后自动触发内容提取（仅对文档类资源）
     * @returns 成功触发提取的文件数（0 表示未触发）
     */
    const triggerAutoExtract = async (
        response: FileBatchUploadResponse | Record<string, unknown> | undefined
    ): Promise<number> => {
        if (!response) return 0
        const projectId = getProjectId()
        if (!projectId) return 0
        const data = (response as { data?: unknown })?.data ?? response
        const uploadedFiles = (data as { uploaded_files?: UploadedFileItem[] })?.uploaded_files
        if (!Array.isArray(uploadedFiles) || uploadedFiles.length === 0) return 0
        // 仅对非 UI 原型图类资源触发提取（UI 原型图走专门的图片处理流程）
        const docFileIds = uploadedFiles
            .filter((f) => f?.id && f.resource_type !== 'ui_mockup')
            .map((f) => f.id)
        if (docFileIds.length === 0) return 0
        try {
            await fileApi.extractContent({ file_ids: docFileIds, project_id: projectId })
            ElMessage.success(`已自动触发 ${docFileIds.length} 个文件的内容提取`)
            // 启动轮询实时跟踪提取状态
            startPolling()
            return docFileIds.length
        } catch {
            ElMessage.warning('部分文件内容提取触发失败，可在列表中手动重试')
            return 0
        }
    }

    /**
     * 手动重试单个文件的内容提取
     * 每次重试递增计数器，达到上限后拒绝继续重试
     */
    const handleRetryExtract = async (fileId: number): Promise<void> => {
        const projectId = getProjectId()
        if (!projectId || !fileId) return
        if (isRetryExhausted(fileId)) {
            ElMessage.warning('重试次数已达上限，请联系管理员')
            return
        }
        // 先递增计数（无论成功与否，重试机会已消耗）
        retryCountMap.value[fileId] = getRetryCount(fileId) + 1
        try {
            await fileApi.extractContent({
                file_ids: [fileId],
                project_id: projectId,
                force_refresh: true,
            })
            ElMessage.success('已重新触发内容提取')
            await getResources()
            startPolling()
        } catch {
            if (isRetryExhausted(fileId)) {
                ElMessage.error('重试次数已达上限（3次），请联系管理员处理')
            } else {
                ElMessage.error('触发内容提取失败')
            }
        }
    }

    return {
        retryCountMap,
        getRetryCount,
        isRetryExhausted,
        MAX_RETRY_COUNT,
        startPolling,
        stopPolling,
        syncPolling,
        triggerAutoExtract,
        handleRetryExtract,
    }
}
