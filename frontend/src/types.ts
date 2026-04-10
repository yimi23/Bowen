// WebSocket message types (server → client)
export type WsMessage =
  | { type: 'routing'; from: string; to: string }
  | { type: 'chunk'; agent: string; content: string }
  | { type: 'tool_call'; agent: string; tool: string; args: Record<string, unknown> }
  | { type: 'tool_result'; agent: string; tool: string; status: string; preview: string }
  | { type: 'done'; agent: string }
  | { type: 'error'; message: string }
  | { type: 'pong' }
  | { type: 'conversation_created'; conversation_id: string; topic_id: string }
  | { type: 'planning_start'; agent: string }
  | { type: 'planning_question'; question: string }
  | { type: 'planning_end' }
  | { type: 'approval_required'; from: string; to: string; action: string; description: string; correlation_id: string }

// WebSocket message types (client → server)
export interface SendMessage {
  type: 'message'
  content: string
  topic_id?: string
  conversation_id?: string
  target_agent?: string
}

export interface PlanningAnswer {
  type: 'planning_answer'
  question: string
  answer: string
}

export interface ApprovalResponse {
  type: 'approval_response'
  correlation_id: string
  approved: boolean
}

// UI state
export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'working'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  agent: string
  content: string
  timestamp: number
}

export interface ToolActivity {
  id: string
  tool: string
  args: Record<string, unknown>
  status: 'running' | 'ok' | 'error'
  preview?: string
}
