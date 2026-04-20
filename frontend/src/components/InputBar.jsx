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

  const isBusy    = micState !== 'idle'
  const isEnded   = disabled
  const canSend   = text.trim() && !isBusy && !isEnded

  const placeholder =
    isEnded       ? 'Session ended. Start a new chat.' :
    micState === 'recording'   ? 'Listening…' :
    micState === 'processing'  ? 'Processing…' :
    micState === 'requesting'  ? 'Requesting mic…' :
    'Ask about products…'

  const handleSend = () => {
    if (!canSend) return
    onSend(text.trim())
    setText('')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  return (
    <div className="flex items-center gap-2 px-3 py-3 bg-white border-t border-gray-100 flex-shrink-0">
      <VoiceMicButton
        micState={micState}
        onStart={onStartRecording}
        onStop={onStopRecording}
        disabled={isEnded}
      />

      <input
        id="chat-input"
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKey}
        disabled={isBusy || isEnded}
        placeholder={placeholder}
        className="flex-1 px-4 py-2 rounded-full bg-gray-50 border border-gray-200 text-sm
                   outline-none focus:ring-2 focus:ring-[#F57224] focus:border-transparent
                   disabled:opacity-50 transition"
      />

      <motion.button
        id="send-btn"
        whileHover={{ scale: canSend ? 1.1 : 1 }}
        whileTap={{ scale: canSend ? 0.9 : 1 }}
        onClick={handleSend}
        disabled={!canSend}
        className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0
                   bg-[#F57224] text-white shadow disabled:opacity-40 disabled:bg-gray-300 transition"
      >
        <Send size={15} />
      </motion.button>
    </div>
  )
}
