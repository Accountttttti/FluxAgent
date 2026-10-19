import type { Role } from '../types'

export interface ApiMessage {
  role: Role
  content: string
}

export interface StreamHandlers {
  onDelta: (text: string) => void
  onTool?: (name: string) => void
}

export async function streamChat(
  messages: ApiMessage[],
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
    signal,
  })

  if (!res.ok || !res.body) {
    throw new Error(`请求失败（${res.status}）`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''

    for (const event of events) {
      const line = event.split('\n').find((l) => l.startsWith('data: '))
      if (!line) continue
      const payload = JSON.parse(line.slice('data: '.length))
      if (payload.delta) handlers.onDelta(payload.delta)
      else if (payload.tool) handlers.onTool?.(payload.tool)
      else if (payload.error) throw new Error(payload.error)
    }
  }
}
