import { useState } from 'react'
import { useChatStore } from '../store/chat'

export function Sidebar() {
  const sessions = useChatStore((s) => s.sessions)
  const currentSessionId = useChatStore((s) => s.currentSessionId)
  const switchSession = useChatStore((s) => s.switchSession)
  const newSession = useChatStore((s) => s.newSession)
  const deleteSession = useChatStore((s) => s.deleteSession)
  const renameSession = useChatStore((s) => s.renameSession)
  const dreaming = useChatStore((s) => s.dreaming)
  const notice = useChatStore((s) => s.notice)
  const dream = useChatStore((s) => s.dream)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')

  const startEdit = (id: string, title: string) => {
    setEditingId(id)
    setDraft(title)
  }

  const commitEdit = () => {
    if (editingId) void renameSession(editingId, draft)
    setEditingId(null)
  }

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">FluxAgent</div>
      <button className="sidebar__new" onClick={newSession}>
        ＋ 新对话
      </button>
      <button
        className="sidebar__dream"
        onClick={() => void dream()}
        disabled={dreaming}
      >
        {dreaming ? '整理中…' : '整理记忆'}
      </button>
      {notice && <div className="sidebar__notice">{notice}</div>}
      <ul className="sidebar__list">
        {sessions.map((s) => (
          <li key={s.id} className="sidebar__row">
            {editingId === s.id ? (
              <input
                className="sidebar__rename"
                value={draft}
                autoFocus
                onChange={(e) => setDraft(e.target.value)}
                onBlur={commitEdit}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') commitEdit()
                  if (e.key === 'Escape') setEditingId(null)
                }}
              />
            ) : (
              <button
                className={`sidebar__item ${
                  s.id === currentSessionId ? 'sidebar__item--active' : ''
                }`}
                onClick={() => void switchSession(s.id)}
                onDoubleClick={() => startEdit(s.id, s.title)}
              >
                {s.title}
              </button>
            )}
            <button
              className="sidebar__delete"
              title="删除会话"
              onClick={() => {
                if (window.confirm('删除这个会话？')) void deleteSession(s.id)
              }}
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
