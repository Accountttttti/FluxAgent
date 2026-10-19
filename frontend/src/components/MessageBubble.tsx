import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import type { Message } from '../types'

// 默认白名单会过滤掉代码高亮的 class，这里放开 hljs 相关类
const schema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [['className', /^hljs$/, /^language-./]],
    span: [['className', /^hljs-/]],
  },
}

export function MessageBubble({ message }: { message: Message }) {
  return (
    <div className={`msg msg--${message.role}`}>
      <div className="msg__avatar">{message.role === 'user' ? '我' : 'AI'}</div>
      <div className="msg__bubble">
        {message.content ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeHighlight, [rehypeSanitize, schema]]}
          >
            {message.content}
          </ReactMarkdown>
        ) : (
          <span className="msg__typing">正在思考…</span>
        )}
      </div>
    </div>
  )
}
