import { useEffect, useRef, useState } from 'react'
import { useChatStore } from '../store/chat'
import { MessageBubble } from './MessageBubble'

export function ChatPanel() {
  const messages = useChatStore((s) => s.messages)
  const streaming = useChatStore((s) => s.streaming)
  const activeTool = useChatStore((s) => s.activeTool)
  const sendMessage = useChatStore((s) => s.sendMessage)
  const stop = useChatStore((s) => s.stop)
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  const submit = () => {
    const text = input.trim()
    if (!text || streaming) return
    setInput('')
    void sendMessage(text)
  }

  return (
    <section className="chat">
      <div className="chat__messages" ref={scrollRef}>
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
      </div>
      {activeTool && (
        <div className="chat__status">正在调用工具：{activeTool}…</div>
      )}
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
