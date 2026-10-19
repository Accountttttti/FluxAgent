import { useEffect, useRef } from 'react'
import { ChatPanel } from './components/ChatPanel'
import { Sidebar } from './components/Sidebar'
import { useChatStore } from './store/chat'
import './App.css'

function App() {
  const init = useChatStore((s) => s.init)
  const inited = useRef(false)

  useEffect(() => {
    if (inited.current) return
    inited.current = true
    void init()
  }, [init])

  return (
    <div className="app">
      <Sidebar />
      <ChatPanel />
    </div>
  )
}

export default App
