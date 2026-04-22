// =============================================================================
// src/components/InputBar.jsx
// Text input + mic button + send button
// =============================================================================
import { useState } from 'react'
import { Send } from 'lucide-react'
import { motion } from 'framer-motion'
import VoiceMicButton from './VoiceMicButton.jsx'

export default function InputBar({ onSend, disabled, micState, onStartRecording, onStopRecording }) {
  const [text, setText] = useState('')
  const [isFocused, setIsFocused] = useState(false)

  const isRecording = micState === 'recording'
  const isBusy    = micState !== 'idle' && !isRecording
  const isEnded   = disabled
  const canSend   = text.trim() && !isBusy && !isEnded

  const handleSend = () => {
    if (!canSend) return
    onSend(text.trim())
    setText('')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  return (
    <div className="flex-shrink-0 relative h-20 w-full max-w-[720px] mx-auto z-20">
      <div className={`
        flex items-center gap-3 p-2 rounded-2xl transition-all duration-300 glass-card glass-shadow
        ${isFocused ? 'ring-[3px] ring-[#F57224]/15 border-[#F57224]' : 'bg-[#3d2a14]'}
      `}>
        
        <VoiceMicButton
          micState={micState}
          onStart={onStartRecording}
          onStop={onStopRecording}
          disabled={isEnded}
        />

        <div className="flex-1 relative flex items-center min-h-[44px]">
          {isRecording ? (
            <div className="flex items-center gap-3 px-4 w-full">
              <div className="flex items-end gap-1 h-3">
                {[0, 1, 2, 3, 4].map(i => (
                  <motion.div
                    key={i}
                    animate={{ height: ['40%', '100%', '40%'] }}
                    transition={{ repeat: Infinity, duration: 0.5 + i * 0.1, ease: 'easeInOut' }}
                    className="w-1 bg-[#F57224] rounded-full"
                  />
                ))}
              </div>
              <span className="text-[10px] font-mono text-[#F57224] animate-pulse uppercase tracking-[0.2em]">
                Recording... tap to stop
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
              disabled={isBusy || isEnded}
              placeholder={isEnded ? "Ledger closed." : "Inquire here..."}
              className="w-full px-4 bg-transparent outline-none text-[#f5ede2] placeholder-[#c4a882]/40 text-sm"
            />
          )}
        </div>

        <motion.button
          id="send-btn"
          whileHover={{ scale: canSend ? 1.05 : 1 }}
          whileTap={{ scale: canSend ? 0.95 : 1 }}
          onClick={handleSend}
          disabled={!canSend}
          className={`
            w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-300
            ${canSend ? 'bg-[#F57224] text-[#1a0f00] shadow-lg shadow-orange-900/20' : 'bg-[#2a1a08] text-[#c4a882]/20 border border-white/5'}
          `}
        >
          <Send size={15} />
        </motion.button>
      </div>
    </div>
  )
}
