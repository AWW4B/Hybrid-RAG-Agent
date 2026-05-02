// =============================================================================
// src/components/InputBar.jsx
// Text input + mic button + send button
// =============================================================================
import { useState } from 'react'
import { Send } from 'lucide-react'
import { motion } from 'framer-motion'
import VoiceMicButton from './VoiceMicButton.jsx'

export default function InputBar({ onSend, disabled, micState, onStartRecording, onStopRecording }) {
  const [text, setText]           = useState('')
  const [isFocused, setIsFocused] = useState(false)

  const state     = micState || 'idle'
  const isRecording = state === 'recording'
  const canSend   = text.trim() && !disabled && state === 'idle'

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
      <VoiceMicButton
        micState={state}
        onStart={onStartRecording}
        onStop={onStopRecording}
        disabled={disabled}
      />

      <div className="flex-1 relative min-w-0">
        {isRecording ? (
          <div className="flex items-center gap-1.5 h-[22px]">
            {[0, 1, 2, 3, 4].map(i => (
              <motion.div
                key={i}
                animate={{ height: ['30%', '100%', '30%'] }}
                transition={{ repeat: Infinity, duration: 0.45 + i * 0.1, ease: 'easeInOut' }}
                className="w-[3px] bg-[#F57224] rounded-full"
                style={{ minHeight: 3 }}
              />
            ))}
            <span className="text-[11px] text-[#F57224] font-mono ml-2 animate-pulse tracking-wide">
              Listening...
            </span>
          </div>
        ) : (
          <input
            id="chat-input"
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKey}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            disabled={disabled || state !== 'idle'}
            placeholder="Message Daraz AI..."
            className="w-full bg-transparent outline-none text-[#f0f0f0] placeholder-[#5a5a5a] text-sm"
          />
        )}
      </div>

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
