import request from '@/utils/request'
import type { ApiResponse } from '@/utils/request'

/**
 * Agent 会话 API 封装（R1-3 可观测性闭环）。
 *
 * 对应后端 app/api/v1/endpoints/agents.py，路由前缀 /api/v1/agents。
 * 提供：会话分页查询、单会话详情、消息流、审计（工具调用）记录、创建并运行会话。
 */

// ============== 类型定义 ==============

/**
 * Agent 类型（与后端 AgentSession.agent_type 合法值一致）。
 * 后端合法值：test_generation / failure_analysis / visual_validation / locator_healing
 */
export type AgentType =
  | 'test_generation'
  | 'failure_analysis'
  | 'visual_validation'
  | 'locator_healing'

/** 会话状态（与后端 AgentSession.status 合法值一致，running 为中间态） */
export type AgentStatus =
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'loop_detected'
  | 'circuit_open'
  | 'token_exhausted'

/** 消息角色（与后端 agent_messages.role 合法值一致） */
export type MessageRole = 'system' | 'user' | 'assistant' | 'tool'

/** Agent 会话（对应后端 SessionResponse） */
export interface AgentSession {
  id: number
  project_id: number
  agent_type: AgentType
  status: AgentStatus
  started_at: string | null
  completed_at: string | null
  token_cost: number
  iteration_count: number
  loop_detected: boolean
  created_by: number | null
}

/** 会话分页列表数据 */
export interface SessionListData {
  items: AgentSession[]
  total: number
}

/** Agent 消息（对应后端 MessageResponse） */
export interface AgentMessage {
  id: number
  session_id: number
  role: MessageRole
  content: Record<string, unknown>
  artifact_refs?: unknown[] | null
  tool_call_id?: string | null
  tool_name?: string | null
  token_cost: number
  created_at: string | null
}

/** Agent 审计（工具调用）记录（对应后端 AuditResponse） */
export interface AgentAudit {
  id: number
  session_id: number
  iteration: number
  action_type: string
  action_detail: Record<string, unknown>
  decision_confidence?: number | null
  /** 0 待审批 / 1 批准 / 2 拒绝 */
  human_approved: number
  approved_by?: number | null
  approved_at?: string | null
  created_at: string | null
}

/** 会话列表查询参数 */
export interface SessionListParams {
  project_id?: number
  agent_type?: AgentType
  status?: AgentStatus
  offset?: number
  limit?: number
}

/** 运行会话请求体（initial_artifacts 元素格式：{artifact_type, data}） */
export interface SessionRunPayload {
  agent_type: AgentType
  project_id: number
  initial_artifacts?: Array<{ artifact_type: string; data: Record<string, unknown> }>
}

// ============== 选项常量（与后端合法值对齐） ==============

/** Agent 类型选项（标签为业务语义，value 为后端枚举值） */
export const agentTypeOptions = [
  { label: '用例生成', value: 'test_generation' },
  { label: '失败分析', value: 'failure_analysis' },
  { label: '视觉校验', value: 'visual_validation' },
  { label: '定位自愈', value: 'locator_healing' },
] as const

/** 会话状态选项 */
export const agentStatusOptions = [
  { label: '运行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '失败', value: 'failed' },
  { label: '已取消', value: 'cancelled' },
  { label: '循环熔断', value: 'loop_detected' },
  { label: '熔断开启', value: 'circuit_open' },
  { label: 'Token耗尽', value: 'token_exhausted' },
] as const

// ============== API 封装 ==============

export const agentApi = {
  /** 分页查询会话列表，支持按项目/Agent类型/状态过滤 */
  getSessions: async (
    params: SessionListParams
  ): Promise<ApiResponse<SessionListData>> => {
    return request.get('/api/v1/agents/sessions', { params })
  },

  /** 查询单个会话详情，不存在返回 404 */
  getSession: async (sessionId: number): Promise<ApiResponse<AgentSession>> => {
    return request.get(`/api/v1/agents/sessions/${sessionId}`)
  },

  /** 按时间升序查询会话消息流（limit 上限 500） */
  getMessages: async (
    sessionId: number,
    limit = 100
  ): Promise<ApiResponse<AgentMessage[]>> => {
    return request.get(`/api/v1/agents/sessions/${sessionId}/messages`, {
      params: { limit },
    })
  },

  /** 查询会话审计（工具调用）记录，按 id 升序返回完整链 */
  getAudits: async (sessionId: number): Promise<ApiResponse<AgentAudit[]>> => {
    return request.get(`/api/v1/agents/sessions/${sessionId}/audits`)
  },

  /** 创建并驱动 Agent 会话运行（R1-2 新增端点，会真实调用 LLM） */
  runSession: async (
    payload: SessionRunPayload
  ): Promise<ApiResponse<AgentSession>> => {
    return request.post('/api/v1/agents/sessions/run', payload)
  },
}

export default agentApi
