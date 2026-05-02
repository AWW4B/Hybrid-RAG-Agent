// =============================================================================
// src/components/SessionSidebar.jsx
// Session list panel — matches backend data shape
// =============================================================================
import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { Plus, Trash2, MessageSquare, RefreshCw } from 'lucide-react'

function relTime(iso) {
  try {
    const diff = Date.now() - new Date(iso).getTime()
    const m = Math.floor(diff / 60000)
    if (m < 1) return 'just now'
    if (m < 60) return `${m}m ago`
    const h = Math.floor(m / 60)
    if (h < 24) return `${h}h ago`
    return `${Math.floor(h / 24)}d ago`
  } catch { return '' }
}

export default function SessionSidebar({
  sessions, currentSessionId, onLoadSession, onNewChat, onDeleteSession, onRefresh, loading
}) {
  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(onRefresh, 30000)
    return () => clearInterval(interval)
  }, [onRefresh])

  return (
    <div className="flex flex-col h-full bg-[#0a0a0a]">
      {/* Header */}
      <div className="p-4 border-b border-white/[0.06]">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-[#f0f0f0]">Chat History</h2>
          <button onClick={onRefresh} disabled={loading}
            className="p-1.5 rounded-md hover:bg-white/[0.06] text-[#5a5a5a] hover:text-[#9a9a9a] transition">
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-semibold
                     border border-[#F57224]/30 text-[#F57224] hover:bg-[#F57224]/[0.06] transition"
        >
          <Plus size={14} /> New Chat
        </button>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto px-3 py-2 custom-scrollbar">
        {loading && sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <div className="w-6 h-6 border-2 border-[#F57224]/20 border-t-[#F57224] rounded-full animate-spin" />
            <span className="text-[11px] text-[#5a5a5a]">Loading...</span>
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-3 px-6 text-center">
            <MessageSquare size={24} className="text-[#2e2e2e]" />
            <p className="text-xs text-[#5a5a5a]">No chats yet. Start a new conversation!</p>
          </div>
        ) : (
          <div className="space-y-1">
            {sessions.map((s) => {
              const isActive = s.session_id === currentSessionId
              return (
                <motion.div
                  key={s.session_id}
                  whileHover={{ x: 2 }}
                  onClick={() => onLoadSession(s.session_id)}
                  className={`group cursor-pointer p-3 rounded-xl transition-all duration-150 flex items-center gap-3
                    ${isActive
                      ? 'bg-[#F57224]/[0.08] border border-[#F57224]/20'
                      : 'hover:bg-white/[0.03] border border-transparent'}`}
                >
                  {/* Indicator */}
                  <div className={`w-1 h-8 rounded-full flex-shrink-0 transition
                    ${isActive ? 'bg-[#F57224]' : 'bg-transparent group-hover:bg-white/10'}`} />

                  <div className="flex-1 min-w-0">
                    <p className={`text-xs font-medium truncate ${isActive ? 'text-[#f0f0f0]' : 'text-[#9a9a9a]'}`}>
                      {s.title || 'New Chat'}
                    </p>
                    <p className="text-[10px] text-[#5a5a5a] font-mono mt-0.5">
                      {relTime(s.updated_at)}
                    </p>
                  </div>

                  {/* Delete button */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      if (confirm('Delete this chat?')) onDeleteSession(s.session_id)
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded-md hover:bg-red-500/10
                               hover:text-red-400 text-[#5a5a5a] transition-all"
                  >
                    <Trash2 size={12} />
                  </button>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
