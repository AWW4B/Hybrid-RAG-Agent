// =============================================================================
// src/components/TypingIndicator.jsx
// 3-dot bounce animation shown while LLM is generating
// =============================================================================
import { motion } from 'framer-motion'

export default function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 8 }}
      className="flex items-end gap-2 px-4 py-1"
    >
      {/* Bot avatar */}
      <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center font-bold text-sm text-white shadow"
        style={{ background: 'linear-gradient(135deg, #F57224, #ff8c42)' }}>
        D
      </div>

      {/* Bubble */}
      <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm border border-gray-100 flex items-center gap-1">
        <span className="typing-dot w-2 h-2 rounded-full bg-gray-400 inline-block" />
        <span className="typing-dot w-2 h-2 rounded-full bg-gray-400 inline-block" />
        <span className="typing-dot w-2 h-2 rounded-full bg-gray-400 inline-block" />
      </div>

      <span className="text-[10px] text-gray-400 pb-1 ml-1">Daraz Assistant is typing…</span>
    </motion.div>
  )
}
