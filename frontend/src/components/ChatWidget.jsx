// =============================================================================
// src/components/ChatWidget.jsx
// Floating action button + spring-animated popup window
// =============================================================================
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageCircle } from 'lucide-react'
import ChatWindow from './ChatWindow.jsx'
import useVoiceChat from '../hooks/useVoiceChat.js'

export default function ChatWidget({ backendStatus, token }) {
  const [isOpen, setIsOpen] = useState(false)
  const chat = useVoiceChat({ token })

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
      {/* Tooltip badge */}
      <AnimatePresence>
        {!isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.9 }}
            transition={{ delay: 1 }}
            className="bg-white text-gray-700 text-xs font-medium px-3 py-2 rounded-2xl shadow-lg
                       border border-gray-100 whitespace-nowrap"
          >
            💬 Need help shopping?
          </motion.div>
        )}
      </AnimatePresence>

      {/* Popup window */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            key="chat-popup"
            initial={{ opacity: 0, scale: 0.8, y: 20, originX: 1, originY: 1 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.8, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
            className="w-[380px] h-[600px] max-[480px]:w-screen max-[480px]:h-screen
                       max-[480px]:fixed max-[480px]:inset-0 max-[480px]:rounded-none"
          >
            <ChatWindow
              chat={chat}
              onMinimize={() => setIsOpen(false)}
              onClose={() => setIsOpen(false)}
              backendStatus={backendStatus}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* FAB */}
      <motion.button
        id="chat-fab"
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        onClick={() => setIsOpen(v => !v)}
        className="w-14 h-14 rounded-full flex items-center justify-center shadow-xl text-white"
        style={{ background: 'linear-gradient(135deg, #F57224, #ff8c42)' }}
        aria-label="Open chat"
      >
        <AnimatePresence mode="wait">
          {isOpen ? (
            <motion.span key="x" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }}
              className="text-xl font-bold">✕</motion.span>
          ) : (
            <motion.span key="msg" initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0, opacity: 0 }}>
              <MessageCircle size={26} />
            </motion.span>
          )}
        </AnimatePresence>
      </motion.button>
    </div>
  )
}
