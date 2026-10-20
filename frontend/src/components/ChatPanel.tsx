import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useChatStore } from '../store/chat'
import type { Message } from '../types'
import { MessageBubble } from './MessageBubble'

const INITIAL_WINDOW = 120
const WINDOW_INCREMENT = 120
const NEAR_BOTTOM_PX = 48
const LOAD_THRESHOLD_PX = 48

// 只取最近 visibleCount 条消息（窗口化），复刻 nanobot 的 windowMessages
function windowMessages(messages: Message[], visibleCount: number): Message[] {
  if (messages.length <= visibleCount) return messages
  return messages.slice(messages.length - visibleCount)
}

export function ChatPanel() {
  const messages = useChatStore((s) => s.messages)
  const streaming = useChatStore((s) => s.streaming)
  const streamingMessageId = useChatStore((s) => s.streamingMessageId)
  const currentSessionId = useChatStore((s) => s.currentSessionId)
  const sendMessage = useChatStore((s) => s.sendMessage)
  const stop = useChatStore((s) => s.stop)
  const [input, setInput] = useState('')
  const [visibleCount, setVisibleCount] = useState(INITIAL_WINDOW)
  const [atBottom, setAtBottom] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)
  const prevScrollHeightRef = useRef(0)

  const visibleMessages = useMemo(
    () => windowMessages(messages, visibleCount),
    [messages, visibleCount],
  )
  const hiddenCount = messages.length - visibleMessages.length

  // 切换会话：重置窗口和滚动位置
  useEffect(() => {
    setVisibleCount(INITIAL_WINDOW)
    setAtBottom(true)
    prevScrollHeightRef.current = 0
  }, [currentSessionId])

  // 在底部时，消息变化自动滚到底（流式、发送、切换）
  useEffect(() => {
    const el = scrollRef.current
    if (el && atBottom) el.scrollTop = el.scrollHeight
  }, [messages, atBottom])

  // 向上加载更多后，补偿 scrollTop，让视口内容不跳动
  useLayoutEffect(() => {
    const el = scrollRef.current
    if (!el || prevScrollHeightRef.current === 0) return
    const delta = el.scrollHeight - prevScrollHeightRef.current
    el.scrollTop += delta
    prevScrollHeightRef.current = 0
  }, [visibleMessages.length])

  const loadEarlier = () => {
    const el = scrollRef.current
    if (el) prevScrollHeightRef.current = el.scrollHeight
    setVisibleCount((c) => Math.min(messages.length, c + WINDOW_INCREMENT))
  }

  const onScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX
    setAtBottom(nearBottom)
    if (el.scrollTop <= LOAD_THRESHOLD_PX && hiddenCount > 0) {
      loadEarlier()
    }
  }

  const submit = () => {
    const text = input.trim()
    if (!text || streaming) return
    setInput('')
    void sendMessage(text)
  }

  return (
    <section className="chat">
      <div className="chat__messages" ref={scrollRef} onScroll={onScroll}>
        {visibleMessages.map((m) => (
          <MessageBubble
            key={m.id}
            message={m}
            streaming={m.id === streamingMessageId}
          />
        ))}
      </div>
      <div className="chat__input">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
          placeholder="输入消息，Enter 发送，Shift+Enter 换行"
        />
        {streaming ? (
          <button onClick={stop}>停止</button>
        ) : (
          <button onClick={submit}>发送</button>
        )}
      </div>
    </section>
  )
}
