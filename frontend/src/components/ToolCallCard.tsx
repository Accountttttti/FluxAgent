import { useState } from 'react'
import type { ToolCall } from '../types'

const RESULT_LIMIT = 1500

function statusText(status: ToolCall['status']): string {
  if (status === 'running') return '运行中…'
  if (status === 'error') return '出错'
  return '完成'
}

export function ToolCallCard({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false)

  const result =
    call.result && call.result.length > RESULT_LIMIT
      ? `${call.result.slice(0, RESULT_LIMIT)}\n…（结果过长，已截断）`
      : call.result

  return (
    <div className={`tool-call tool-call--${call.status}`}>
      <button
        className="tool-call__header"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="tool-call__dot" />
        <span className="tool-call__name">{call.name}</span>
        <span className="tool-call__status">{statusText(call.status)}</span>
        <span className="tool-call__chevron">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="tool-call__body">
          {call.arguments && (
            <>
              <div className="tool-call__label">参数</div>
              <pre>{call.arguments}</pre>
            </>
          )}
          {call.result !== undefined && (
            <>
              <div className="tool-call__label">结果</div>
              <pre>{result || '（无输出）'}</pre>
            </>
          )}
        </div>
      )}
    </div>
  )
}
