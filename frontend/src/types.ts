export type Role = 'user' | 'assistant'

export interface Session {
  id: string
  title: string
  createdAt: number
  updatedAt: number
}

export interface ToolCall {
  id: string
  name: string
  arguments?: string
  result?: string
  status: 'running' | 'done' | 'error'
}

export interface Message {
  id: string
  sessionId: string
  role: Role
  content: string
  createdAt: number
  toolCalls?: ToolCall[]
}
