import request from '@/utils/request'
import type { ApiResponse } from '@/utils/request'

// ============== 快速测试类型 ==============

/** 快速测试启动请求：被测站点 URL + 可选描述/登录凭据 */
export interface QuickTestLaunchRequest {
    url: string
    description?: string
    credentials?: {
        username: string
        password: string
    }
}

/** 快速测试启动响应：编排完成后返回任务 ID 与 WebSocket 订阅通道 */
export interface QuickTestLaunchResponse {
    task_id: number
    project_id: number
    estimated_duration_sec: number
    websocket_channel: string
}

/**
 * 快速测试编排阶段标识。
 * 与后端 QuickLauncher 推送阶段对齐，前端据此定位进度条位置。
 */
export type QuickTestStage =
    | 'pending'
    | 'site_exploring'
    | 'case_generating'
    | 'task_assembling'
    | 'executing'
    | 'completed'
    | 'failed'
    | 'stopped'

/** 快速测试任务状态查询响应 */
export interface QuickTestStatusResponse {
    task_id: number
    /** 后端返回中文标签：等待执行/执行中/执行完成/执行失败/已停止 */
    status: string
    progress: number
    current_stage: QuickTestStage
    case_count: number
    started_at: string | null
    websocket_channel: string
}

// ============== 快速测试 API ==============
// 真实后端：POST /api/v1/quick-test/launch、GET /api/v1/quick-test/{task_id}/status
// baseURL 默认为空，此处显式带 /api/v1 前缀，与 src/api/project.ts、testTask.ts 风格一致
const quickTestApi = {
    /** 启动快速测试：建项→探索→生成→任务装配，返回 task_id 与 WebSocket 通道。
     *  显式设置 300s 超时：launch 含站点探索（多页 BFS）+ AI 用例生成 + 任务编排，
     *  实测 30s+，默认 30s 超时会导致请求被 abort 收不到响应（spec SLA ≤5 分钟）。
     */
    launch: async (
        data: QuickTestLaunchRequest
    ): Promise<ApiResponse<QuickTestLaunchResponse>> => {
        return request.post('/api/v1/quick-test/launch', data, {
            timeout: 300000,
        })
    },

    /** 查询快速测试任务进度（断线重连/轮询场景使用） */
    getStatus: async (
        taskId: number
    ): Promise<ApiResponse<QuickTestStatusResponse>> => {
        return request.get(`/api/v1/quick-test/${taskId}/status`)
    },
}

export default quickTestApi
export const QuickTestApi = quickTestApi
