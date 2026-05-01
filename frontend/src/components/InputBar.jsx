// =============================================================================
// src/components/InputBar.jsx
// Modern text input + send button
// =============================================================================
import { useState } from 'react'
import { Send } from 'lucide-react'
import { motion } from 'framer-motion'

export default function InputBar({ onSend, disabled }) {
  const [text, setText] = useState('')
  const [isFocused, setIsFocused] = useState(false)

  const canSend = text.trim() && !disabled

  const handleSend = () => {
    if (!canSend) return
    onSend(text.trim())
    setText('')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className={`
      flex items-center gap-2 px-4 py-2.5 rounded-2xl transition-all duration-200
      bg-[#141414] border
      ${isFocused ? 'border-[#F57224]/30 ring-1 ring-[#F57224]/10' : 'border-white/[0.08]'}
    `}>
      <input
        id="chat-input"
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKey}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        disabled={disabled}
        placeholder="Message Daraz AI..."
        className="flex-1 bg-transparent outline-none text-[#f0f0f0] placeholder-[#5a5a5a] text-sm"
      />

      <motion.button
        id="send-btn"
        whileHover={{ scale: canSend ? 1.05 : 1 }}
        whileTap={{ scale: canSend ? 0.95 : 1 }}
        onClick={handleSend}
        disabled={!canSend}
        className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-200
          ${canSend
            ? 'bg-[#F57224] text-white shadow-md shadow-[#F57224]/20'
            : 'bg-[#1a1a1a] text-[#5a5a5a]'}`}
      >
        <Send size={14} />
      </motion.button>
    </div>
  )
}
