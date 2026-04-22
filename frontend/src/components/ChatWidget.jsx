// =============================================================================
// src/components/ChatWidget.jsx
// Floating action button + spring-animated popup window
// =============================================================================
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageCircle } from 'lucide-react'
import ChatWindow from './ChatWindow.jsx'
import useVoiceChat from '../hooks/useVoiceChat.js'

export default function ChatWidget({ backendStatus, token, user }) {
  const [isOpen, setIsOpen] = useState(false)
  const chat = useVoiceChat({ token })

  return (
    <div className="fixed bottom-8 right-8 z-50 flex flex-col items-end gap-4 overflow-visible">
      {/* Tooltip badge */}
      <AnimatePresence>
        {!isOpen && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ delay: 1.5 }}
            className="bg-[#2a1a08] border border-[#ff8c42]/20 text-[#c4a882] text-[10px] font-bold uppercase tracking-widest px-4 py-2 rounded-xl glass-shadow whitespace-nowrap mb-2"
          >
            Consult with the Merchant
          </motion.div>
        )}
      </AnimatePresence>

      {/* Popup window */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            key="chat-popup"
            initial={{ opacity: 0, scale: 0.9, y: 40, originX: 1, originY: 1 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 40 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            className="w-[400px] h-[640px] max-[480px]:w-screen max-[480px]:h-screen
                       max-[480px]:fixed max-[480px]:inset-0 max-[480px]:rounded-none
                       glass-card rounded-[2rem] overflow-hidden glass-shadow mb-4"
          >
            <div className="h-full w-full backdrop-blur-[20px] bg-[#1a0f00]/40">
              <ChatWindow
                chat={chat}
                onMinimize={() => setIsOpen(false)}
                onClose={() => setIsOpen(false)}
                backendStatus={backendStatus}
                user={user}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* FAB */}
      <motion.button
        id="chat-fab"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setIsOpen(v => !v)}
        className="relative w-16 h-16 rounded-[1.5rem] flex items-center justify-center shadow-2xl transition-all duration-500 overflow-visible"
        style={{ background: 'linear-gradient(135deg, #F57224, #ff8c42)' }}
        aria-label="Toggle chat"
      >
        {/* Glow Ring */}
        {!isOpen && (
          <div className="absolute inset-[-4px] rounded-[1.8rem] border border-[#F57224]/30 animate-glow-pulse" />
        )}

        <AnimatePresence mode="wait">
          {isOpen ? (
            <motion.span key="x" initial={{ rotate: -45, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 45, opacity: 0 }}
              className="text-[#1a0f00] font-bold text-xl uppercase tracking-tighter">✕</motion.span>
          ) : (
            <motion.div key="d" initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.8, opacity: 0 }}
              className="flex flex-col items-center">
              <span className="text-[#1a0f00] font-serif font-black italic text-3xl leading-none px-1">D</span>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.button>
    </div>
  )
}
