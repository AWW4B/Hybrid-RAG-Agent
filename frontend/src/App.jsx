// =============================================================================
// src/App.jsx
// Root — handles auth state, renders Login or Chat layout directly
// =============================================================================
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { LogOut, Plus, PanelLeftClose, PanelLeft, ShoppingBag } from 'lucide-react'
import useAuth from './hooks/useAuth.js'
import useChat from './hooks/useVoiceChat.js'
import LoginPage from './components/LoginPage.jsx'
import ChatWindow from './components/ChatWindow.jsx'
import SessionSidebar from './components/SessionSidebar.jsx'
import { healthCheck } from './utils/api.js'
import './App.css'

export default function App() {
  const { authState, authError, isLoading, user, isAdmin, login, logout } = useAuth()
  const [backendStatus, setBackendStatus] = useState('checking')
  const [sidebarOpen, setSidebarOpen]     = useState(true)

  // Poll backend health
  useEffect(() => {
    healthCheck()
      .then(() => setBackendStatus('online'))
      .catch(() => setBackendStatus('offline'))
  }, [])

  // Loading state
  if (authState === 'unknown') {
    return (
      <div className="h-screen flex items-center justify-center bg-[#0a0a0a]">
        <div className="w-10 h-10 rounded-full border-[3px] border-[#F57224] border-t-transparent animate-spin" />
      </div>
    )
  }

  // Login
  if (authState === 'unauthenticated') {
    return <LoginPage onLogin={login} error={authError} isLoading={isLoading} />
  }

  // Chat layout
  return <ChatLayout user={user} logout={logout} backendStatus={backendStatus} sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
}

function ChatLayout({ user, logout, backendStatus, sidebarOpen, setSidebarOpen }) {
  const chat = useChat({ user })

  return (
    <div className="h-screen flex bg-[#0a0a0a] overflow-hidden">
      {/* Sidebar */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 280, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="flex-shrink-0 overflow-hidden border-r border-white/[0.06]"
          >
            <SessionSidebar
              sessions={chat.sessions}
              currentSessionId={chat.sessionId}
              onLoadSession={chat.loadSession}
              onNewChat={chat.newChat}
              onDeleteSession={chat.removeSession}
              onRefresh={chat.refreshSessions}
              loading={chat.sessionsLoading}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="flex items-center gap-3 px-4 h-14 border-b border-white/[0.06] bg-[#0a0a0a] flex-shrink-0 z-20">
          <button
            onClick={() => setSidebarOpen(v => !v)}
            className="p-2 rounded-lg hover:bg-white/[0.06] text-[#9a9a9a] hover:text-white transition"
            title={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          >
            {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
          </button>

          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #F57224, #ff6b35)' }}>
              <ShoppingBag size={14} className="text-white" />
            </div>
            <span className="text-sm font-semibold text-[#f0f0f0]">Daraz AI</span>
          </div>

          {/* Status dot */}
          <div className="flex items-center gap-1.5 ml-1">
            <span className={`w-1.5 h-1.5 rounded-full ${
              backendStatus === 'online' ? 'bg-emerald-400' :
              backendStatus === 'offline' ? 'bg-red-400' : 'bg-yellow-400'
            }`} />
            <span className="text-[10px] text-[#5a5a5a] font-medium capitalize">{backendStatus}</span>
          </div>

          <div className="flex-1" />

          {/* New chat button */}
          <button
            onClick={chat.newChat}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                       text-[#9a9a9a] hover:text-white hover:bg-white/[0.06] transition"
          >
            <Plus size={14} /> New Chat
          </button>

          {/* User chip */}
          {user?.username && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
              <div className="w-5 h-5 rounded-full bg-gradient-to-br from-[#F57224] to-[#ff6b35] flex items-center justify-center">
                <span className="text-[9px] font-bold text-white uppercase">{user.username[0]}</span>
              </div>
              <span className="text-xs text-[#9a9a9a] font-medium">{user.username}</span>
            </div>
          )}

          <button
            onClick={logout}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                       text-red-400/70 hover:text-red-400 hover:bg-red-500/[0.06] transition"
          >
            <LogOut size={13} /> Logout
          </button>
        </header>

        {/* Chat window */}
        <div className="flex-1 min-h-0">
          <ChatWindow chat={chat} backendStatus={backendStatus} />
        </div>
      </div>
    </div>
  )
}
