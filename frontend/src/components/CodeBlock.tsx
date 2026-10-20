import { memo, useEffect, useRef, useState } from 'react'
import hljs from 'highlight.js/lib/common'

interface CodeBlockProps {
  language?: string
  code: string
  streaming?: boolean
}

// 复刻 nanobot 的 CodeBlock：代码块「进入视口才高亮」+「流式期间不高亮」。
// 高亮是 CPU 重活（highlight.js），屏幕外 / 没闭合的代码块都先渲染成纯 <pre>。
export const CodeBlock = memo(function CodeBlock({
  language,
  code,
  streaming = false,
}: CodeBlockProps) {
  const ref = useRef<HTMLPreElement>(null)
  const [inView, setInView] = useState(false)
  const [html, setHtml] = useState<string | null>(null)

  // 进入视口（或距视口 300px 内）才标记为「可高亮」
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (typeof IntersectionObserver === 'undefined') {
      setInView(true)
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setInView(true)
          observer.disconnect()
        }
      },
      { rootMargin: '300px' },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  // 高亮时机：进入视口 && 不在流式（等代码块闭合）
  useEffect(() => {
    if (!inView || streaming) return
    const value =
      language && hljs.getLanguage(language)
        ? hljs.highlight(code, { language, ignoreIllegals: true }).value
        : hljs.highlightAuto(code).value
    setHtml(value)
  }, [inView, streaming, language, code])

  return (
    <pre ref={ref} className="codeblock">
      {html ? (
        <code
          className={`hljs${language ? ` language-${language}` : ''}`}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <code className={language ? `language-${language}` : undefined}>{code}</code>
      )}
    </pre>
  )
})
