import { memo } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import type { Message } from '../types'
import { CodeBlock } from './CodeBlock'
import { ToolCallCard } from './ToolCallCard'

// 放开 language-* class，让代码块能拿到语言；hljs 的 span 由 CodeBlock 组件自己生成，不走 sanitize
const schema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [['className', /^language-./]],
  },
}

export const MessageBubble = memo(function MessageBubble({
  message,
  streaming = false,
}: {
  message: Message
  streaming?: boolean
}) {
  const toolCalls = message.toolCalls ?? []

  return (
    <div className={`msg msg--${message.role}`}>
      <div className="msg__avatar">{message.role === 'user' ? '我' : 'AI'}</div>
      <div className="msg__column">
        {toolCalls.map((tc) => (
          <ToolCallCard key={tc.id} call={tc} />
        ))}
        <div className="msg__bubble">
          {message.content ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[[rehypeSanitize, schema]]}
              components={{
                pre: ({ children }) => <>{children}</>,
                code: ({ className, children }) => {
                  const match = /language-(\w+)/.exec(className || '')
                  const text = String(children)
                  const isBlock = Boolean(match) || text.includes('\n')
                  if (!isBlock) {
                    return <code className={className}>{children}</code>
                  }
                  return (
                    <CodeBlock
                      language={match?.[1]}
                      code={text.replace(/\n$/, '')}
                      streaming={streaming}
                    />
                  )
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          ) : toolCalls.length === 0 ? (
            <span className="msg__typing">正在思考…</span>
          ) : null}
        </div>
      </div>
    </div>
  )
})
