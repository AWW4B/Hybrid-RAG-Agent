// =============================================================================
// src/components/SessionSidebar.jsx
// Slide-in chat history panel from the left
// =============================================================================
import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, ArrowLeft, Trash2, MessageSquare } from 'lucide-react'
import { getSessions, deleteSession } from '../utils/api.js'

function relTime(iso) {
  try {
    const diff = Date.now() - new Date(iso).getTime()
    const m = Math.floor(diff / 60000)
    if (m < 1)  return 'just now'
    if (m < 60) return `${m}m ago`
    const h = Math.floor(m / 60)
    if (h < 24) return `${h}h ago`
    return `${Math.floor(h / 24)}d ago`
  } catch { return '' }
}

export default function SessionSidebar({ currentSessionId, onLoadSession, onNewChat, isOpen, onClose }) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading]   = useState(false)

  useEffect(() => {
    if (!isOpen) return
    setLoading(true)
    getSessions()
      .then(({ sessions: s }) => setSessions(s || []))
      .catch(() => setSessions([]))
      .finally(() => setLoading(false))
  }, [isOpen])

  const handleDelete = async (e, sid) => {
    e.stopPropagation()
    await deleteSession(sid).catch(() => {})
    setSessions(prev => prev.filter(s => s.session_id !== sid))
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/30 backdrop-blur-sm z-[60]"
          />

          {/* Panel */}
          <motion.div
            key="panel"
            initial={{ x: -320 }} animate={{ x: 0 }} exit={{ x: -320 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed left-0 top-0 bottom-0 w-80 bg-white z-[70] flex flex-col shadow-2xl"
          >
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-4 bg-gradient-to-r from-[#F57224] to-[#ff8c42]">
              <motion.button
                whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
                onClick={onClose}
                className="p-1.5 rounded-full hover:bg-white/20 text-white"
              >
                <ArrowLeft size={18} />
              </motion.button>
              <span className="text-white font-semibold flex-1">Chat History</span>
              <motion.button
                whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
                onClick={() => { onNewChat(); onClose() }}
                className="p-1.5 rounded-full hover:bg-white/20 text-white"
                title="New chat"
              >
                <Plus size={18} />
              </motion.button>
            </div>

            {/* Session list */}
            <div className="flex-1 overflow-y-auto chat-scroll">
              {loading ? (
                <div className="flex items-center justify-center py-12 text-gray-400 text-sm">Loading…</div>
              ) : sessions.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-gray-400 gap-2">
                  <MessageSquare size={32} className="opacity-40" />
                  <span className="text-sm">No previous sessions</span>
                </div>
              ) : (
                <div className="p-3 space-y-1">
                  {sessions.map((s) => {
                    const isActive = s.session_id === currentSessionId
                    return (
                      <motion.div
                        key={s.session_id}
                        whileHover={{ x: 4 }}
                        onClick={() => { onLoadSession(s.session_id); onClose() }}
                        className={`group relative flex flex-col gap-0.5 px-3 py-3 rounded-xl cursor-pointer transition
                                    ${isActive
                                      ? 'bg-orange-50 border-l-4 border-l-[#F57224]'
                                      : 'hover:bg-gray-50 border-l-4 border-l-transparent'}`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-medium text-gray-800 truncate">
                            {s.title || `Session ${s.session_id.slice(0, 8)}`}
                          </span>
                          {s.status === 'ended' && (
                            <span className="text-[9px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full flex-shrink-0">
                              Ended
                            </span>
                          )}
                        </div>
                        <span className="text-[11px] text-gray-400 truncate">
                          {s.preview || 'No messages yet'}
                        </span>
                        <div className="flex items-center justify-between mt-0.5">
                          <span className="text-[10px] text-gray-300">{relTime(s.created_at)}</span>
                          <span className="text-[10px] text-gray-300">{s.turns}/{s.turns_max} turns</span>
                        </div>

                        {/* Delete */}
                        <button
                          onClick={(e) => handleDelete(e, s.session_id)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-full
                                     text-gray-300 hover:text-red-500 hover:bg-red-50
                                     opacity-0 group-hover:opacity-100 transition"
                          title="Delete session"
                        >
                          <Trash2 size={13} />
                        </button>
                      </motion.div>
                    )
                  })}
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
