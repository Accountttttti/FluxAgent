import { create } from 'zustand'
import { db } from '../lib/db'
import { streamChat, type ApiMessage } from '../lib/api'
import type { Message, Session } from '../types'

function makeId(): string {
  return crypto.randomUUID()
}

interface ChatState {
  sessions: Session[]
  currentSessionId: string | null
  messages: Message[]
  streaming: boolean
  activeTool: string | null
  error: string | null

  init: () => Promise<void>
  newSession: () => Promise<void>
  switchSession: (id: string) => Promise<void>
  sendMessage: (content: string) => Promise<void>
  deleteSession: (id: string) => Promise<void>
  renameSession: (id: string, title: string) => Promise<void>
  stop: () => void
}

let abortController: AbortController | null = null

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  currentSessionId: null,
  messages: [],
  streaming: false,
  activeTool: null,
  error: null,

  init: async () => {
    const sessions = await db.sessions.orderBy('updatedAt').reverse().toArray()
    if (sessions.length === 0) {
      await get().newSession()
      return
    }
    set({ sessions })
    await get().switchSession(sessions[0].id)
  },

  newSession: async () => {
    const now = Date.now()
    const session: Session = {
      id: makeId(),
      title: '新对话',
      createdAt: now,
      updatedAt: now,
    }
    await db.sessions.add(session)
    set((state) => ({
      sessions: [session, ...state.sessions],
      currentSessionId: session.id,
      messages: [],
      error: null,
    }))
  },

  switchSession: async (id: string) => {
    const messages = await db.messages
      .where('sessionId')
      .equals(id)
      .sortBy('createdAt')
    set({ currentSessionId: id, messages, error: null })
  },

  deleteSession: async (id: string) => {
    await db.messages.where('sessionId').equals(id).delete()
    await db.sessions.delete(id)
    const remaining = get().sessions.filter((s) => s.id !== id)
    set({ sessions: remaining })
    if (get().currentSessionId === id) {
      if (remaining.length > 0) {
        await get().switchSession(remaining[0].id)
      } else {
        await get().newSession()
      }
    }
  },

  renameSession: async (id: string, title: string) => {
    const t = title.trim()
    if (!t) return
    await db.sessions.update(id, { title: t })
    set((state) => ({
      sessions: state.sessions.map((s) => (s.id === id ? { ...s, title: t } : s)),
    }))
  },

  sendMessage: async (content: string) => {
    const sessionId = get().currentSessionId
    if (!sessionId || get().streaming) return

    // 第一条消息自动作为会话标题
    if (get().messages.length === 0) {
      const title = content.replace(/\s+/g, ' ').trim().slice(0, 20) || '新对话'
      await db.sessions.update(sessionId, { title })
      set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === sessionId ? { ...s, title } : s,
        ),
      }))
    }

    const userMsg: Message = {
      id: makeId(),
      sessionId,
      role: 'user',
      content,
      createdAt: Date.now(),
    }
    const assistantMsg: Message = {
      id: makeId(),
      sessionId,
      role: 'assistant',
      content: '',
      createdAt: Date.now() + 1,
    }
    await db.messages.add(userMsg)

    // 只带最近 20 条历史（窗口化），既省 token 又避免超长上下文
    const apiMessages: ApiMessage[] = [...get().messages, userMsg]
      .filter((m) => m.content)
      .slice(-20)
      .map((m) => ({ role: m.role, content: m.content }))

    set((state) => ({
      messages: [...state.messages, userMsg, assistantMsg],
      streaming: true,
      error: null,
    }))

    abortController = new AbortController()
    let buffer = ''
    let rafId: number | null = null

    // rAF 批处理：把一帧内到达的 token 攒起来，每帧只更新一次界面
    const flush = () => {
      rafId = null
      const text = buffer
      buffer = ''
      if (text) {
        set((state) => ({
          messages: state.messages.map((m) =>
            m.id === assistantMsg.id ? { ...m, content: m.content + text } : m,
          ),
        }))
      }
    }

    try {
      await streamChat(
        apiMessages,
        {
          onDelta: (delta) => {
            if (get().activeTool) set({ activeTool: null })
            buffer += delta
            if (rafId === null) rafId = requestAnimationFrame(flush)
          },
          onTool: (name) => set({ activeTool: name }),
        },
        abortController.signal,
      )
    } catch (err) {
      if (!abortController.signal.aborted) {
        set({ error: err instanceof Error ? err.message : String(err) })
      }
    } finally {
      if (rafId !== null) cancelAnimationFrame(rafId)
      flush()
      const finalContent =
        get().messages.find((m) => m.id === assistantMsg.id)?.content ?? ''
      await db.messages.add({ ...assistantMsg, content: finalContent })
      await db.sessions.update(sessionId, { updatedAt: Date.now() })
      abortController = null
      set({ streaming: false, activeTool: null })
    }
  },

  stop: () => {
    abortController?.abort()
  },
}))
