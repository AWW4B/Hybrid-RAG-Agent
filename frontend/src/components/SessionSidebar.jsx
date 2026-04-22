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

export default function SessionSidebar({ currentSessionId, onLoadSession, onNewChat, isOpen, onClose, isStatic }) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!isOpen) return
    
    const fetch = () => {
      getSessions()
        .then(({ sessions: s }) => setSessions(s || []))
        .catch(() => setSessions([]))
        .finally(() => setLoading(false))
    }

    setLoading(true)
    fetch()

    const interval = setInterval(fetch, 10000)
    return () => clearInterval(interval)
  }, [isOpen, currentSessionId])

  const handleDelete = async (e, sid) => {
    e.stopPropagation()
    if (!confirm('Discard this ledger?')) return
    try {
      await deleteSession(sid)
      setSessions(prev => prev.filter(s => s.session_id !== sid))
    } catch (err) {
      alert('Failed to discard ledger')
    }
  }

  const sidebarContent = (
    <div className="flex flex-col h-full bg-[#2a1a08] border-r border-white/5 text-[#f5ede2]">
      {/* Header */}
      <div className="p-6">
        <h2 className="font-serif italic text-2xl font-bold text-[#f5ede2] mb-1">
          Merchant Ledger
        </h2>
        <p className="text-[10px] uppercase tracking-[0.2em] text-[#c4a882] mb-6 font-mono">
          Session Chronicles
        </p>
        
        <motion.button
          whileHover={{ scale: 1.02, backgroundColor: 'rgba(245, 114, 36, 0.1)' }}
          whileTap={{ scale: 0.98 }}
          onClick={() => {
            onNewChat();
            if (!isStatic) onClose();
          }}
          className="w-full py-3 px-4 rounded-xl border border-[#F57224]/40 text-[#F57224] text-xs font-bold uppercase tracking-widest transition-all"
        >
          Begin New Bargain
        </motion.button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-4 pb-6 custom-scrollbar">
        {loading && sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 gap-4">
             <div className="w-8 h-8 border-[3px] border-[#F57224]/20 border-t-[#F57224] rounded-full animate-spin" />
             <span className="text-[10px] uppercase font-bold tracking-[0.2em] text-[#c4a882] opacity-40">Recalling Chronicles...</span>
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 px-8 text-center gap-4">
            <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center border border-white/5 opacity-20 mb-2">
              <MessageSquare size={32} className="text-[#c4a882]" />
            </div>
            <p className="text-[10px] font-bold text-[#c4a882] uppercase tracking-[0.2em] leading-relaxed">
              No archives found.<br/>
              <span className="opacity-40 italic font-medium lowercase">The ledger is currently blank.</span>
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map((s) => {
              const isActive = s.session_id === currentSessionId
              return (
                <motion.div
                  key={s.session_id}
                  whileHover={{ x: 4, backgroundColor: 'rgba(255, 255, 255, 0.02)' }}
                  onClick={() => {
                    onLoadSession(s.session_id)
                    if (!isStatic) onClose()
                  }}
                  className={`relative group cursor-pointer p-4 rounded-[1.5rem] transition-all duration-300 ${
                    isActive 
                      ? 'bg-[#F57224]/10 border border-[#F57224]/20 shadow-[0_0_24px_rgba(245,114,36,0.08)]' 
                      : 'bg-white/5 border border-white/5 hover:border-white/10'
                  }`}
                >
                  <div className={`absolute left-0 top-4 bottom-4 w-1 rounded-full transition-all duration-300 ${
                    isActive ? 'bg-[#F57224] opacity-100' : 'bg-[#F57224]/20 opacity-0 group-hover:opacity-100'
                  }`} />

                  <div className="flex flex-col gap-1">
                    <div className="flex justify-between items-start gap-2">
                       <span className={`font-serif italic text-sm line-clamp-1 ${isActive ? 'text-[#f5ede2]' : 'text-[#c4a882]'}`}>
                         {s.title || 'New Bargain'}
                       </span>
                       <button
                         onClick={(e) => handleDelete(e, s.session_id)}
                         className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-500 transition-all text-[#c4a882]"
                       >
                         <Trash2 size={12} />
                       </button>
                    </div>
                    
                    <span className="font-mono text-[9px] uppercase text-[#c4a882]/50">
                      {new Date(s.updated_at).toLocaleDateString()} · {s.turns} TURNS
                    </span>
                    
                    {s.preview && (
                      <p className="text-[11px] text-[#c4a882] line-clamp-1 leading-relaxed opacity-60 font-sans mt-0.5">
                        {s.preview}
                      </p>
                    )}
                  </div>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )

  if (isStatic) return (
    <div className="h-full w-full overflow-hidden">
      {sidebarContent}
    </div>
  )

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[70]">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          />
          {/* Drawer */}
          <motion.div
            initial={{ x: '-100%' }} animate={{ x: 0 }} exit={{ x: '-100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="absolute left-0 top-0 bottom-0 w-[300px] shadow-2xl"
          >
            {sidebarContent}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
