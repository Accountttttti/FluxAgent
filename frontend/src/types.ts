export type Role = 'user' | 'assistant'

export interface Session {
  id: string
  title: string
  createdAt: number
  updatedAt: number
}

export interface Message {
  id: string
  sessionId: string
  role: Role
  content: string
  createdAt: number
}
