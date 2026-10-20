import { create } from 'zustand'
import { db } from '../lib/db'
import { streamChat, dream as dreamApi, type ApiMessage } from '../lib/api'
import type { Message, Session, ToolCall } from '../types'

function makeId(): string {
  return crypto.randomUUID()
}

interface ChatState {
  sessions: Session[]
  currentSessionId: string | null
  messages: Message[]
  streaming: boolean
  streamingMessageId: string | null
  error: string | null
  dreaming: boolean
  notice: string | null

  init: () => Promise<void>
  newSession: () => Promise<void>
  switchSession: (id: string) => Promise<void>
  sendMessage: (content: string) => Promise<void>
  deleteSession: (id: string) => Promise<void>
  renameSession: (id: string, title: string) => Promise<void>
  stop: () => void
  dream: () => Promise<void>
}

let abortController: AbortController | null = null

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  currentSessionId: null,
  messages: [],
  streaming: false,
  streamingMessageId: null,
  error: null,
  dreaming: false,
  notice: null,

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
      streamingMessageId: assistantMsg.id,
      error: null,
    }))

    abortController = new AbortController()
    let buffer = ''
    let rafId: number | null = null
    let timerId: number | null = null
    let lastFlush = 0
    // 最多每 50ms 刷一次屏，给 markdown 解析和布局留出时间（nanobot 的做法）
    const FLUSH_INTERVAL_MS = 50

    // 把攒起来的 token 一次性写进界面
    const flush = () => {
      rafId = null
      timerId = null
      const text = buffer
      buffer = ''
      lastFlush = performance.now()
      if (text) {
        set((state) => ({
          messages: state.messages.map((m) =>
            m.id === assistantMsg.id ? { ...m, content: m.content + text } : m,
          ),
        }))
      }
    }

    // 50ms 节流调度：距上次刷屏不足 50ms 就用定时器等到点，否则下一帧就刷
    const schedule = () => {
      if (rafId !== null || timerId !== null) return
      const delay = FLUSH_INTERVAL_MS - (performance.now() - lastFlush)
      if (delay > 0) {
        timerId = window.setTimeout(() => {
          timerId = null
          schedule()
        }, delay)
        return
      }
      rafId = requestAnimationFrame(flush)
    }

    try {
      await streamChat(
        apiMessages,
        {
          onDelta: (delta) => {
            buffer += delta
            schedule()
          },
          onTool: (name, args) => {
            const toolCall: ToolCall = {
              id: makeId(),
              name,
              arguments:
                args && Object.keys(args).length > 0
                  ? JSON.stringify(args, null, 2)
                  : undefined,
              status: 'running',
            }
            set((state) => ({
              messages: state.messages.map((m) =>
                m.id === assistantMsg.id
                  ? { ...m, toolCalls: [...(m.toolCalls ?? []), toolCall] }
                  : m,
              ),
            }))
          },
          onToolResult: (result, error) => {
            set((state) => ({
              messages: state.messages.map((m) => {
                if (m.id !== assistantMsg.id) return m
                const calls = [...(m.toolCalls ?? [])]
                let idx = -1
                for (let i = calls.length - 1; i >= 0; i--) {
                  if (calls[i].status === 'running') {
                    idx = i
                    break
                  }
                }
                if (idx >= 0) {
                  calls[idx] = { ...calls[idx], result, status: error ? 'error' : 'done' }
                }
                return { ...m, toolCalls: calls }
              }),
            }))
          },
        },
        abortController.signal,
      )
    } catch (err) {
      if (!abortController.signal.aborted) {
        set({ error: err instanceof Error ? err.message : String(err) })
      }
    } finally {
      if (rafId !== null) cancelAnimationFrame(rafId)
      if (timerId !== null) clearTimeout(timerId)
      flush()
      const finalMsg = get().messages.find((m) => m.id === assistantMsg.id)
      const finalContent = finalMsg?.content ?? ''
      const finalToolCalls = finalMsg?.toolCalls
      await db.messages.add({ ...assistantMsg, content: finalContent, toolCalls: finalToolCalls })
      await db.sessions.update(sessionId, { updatedAt: Date.now() })
      abortController = null
      set({ streaming: false, streamingMessageId: null })
    }
  },

  stop: () => {
    abortController?.abort()
  },

  dream: async () => {
    if (get().dreaming) return
    set({ dreaming: true, notice: null })
    try {
      const result = await dreamApi()
      set({ notice: result })
    } catch (err) {
      set({ notice: err instanceof Error ? err.message : String(err) })
    } finally {
      set({ dreaming: false })
      setTimeout(() => set({ notice: null }), 6000)
    }
  },
}))
