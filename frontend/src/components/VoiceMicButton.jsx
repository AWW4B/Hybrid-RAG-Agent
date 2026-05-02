// =============================================================================
// src/components/VoiceMicButton.jsx
// Recording state machine button with animated pulse rings
// States: idle | requesting | recording | processing
// =============================================================================
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, Loader2 } from 'lucide-react'

export default function VoiceMicButton({ micState, onStart, onStop, disabled }) {
  const isRecording  = micState === 'recording'
  const isProcessing = micState === 'processing' || micState === 'requesting'

  const handleClick = () => {
    if (disabled || isProcessing) return
    if (isRecording) onStop?.()
    else onStart?.()
  }

  return (
    <div className="relative flex items-center justify-center">
      {isRecording && (
        <>
          <motion.div
            animate={{ scale: [1, 1.8], opacity: [0.5, 0] }}
            transition={{ repeat: Infinity, duration: 2 }}
            className="absolute w-8 h-8 rounded-full bg-[#F57224] z-0"
          />
          <motion.div
            animate={{ scale: [1, 1.4], opacity: [0.3, 0] }}
            transition={{ repeat: Infinity, duration: 1.5, delay: 0.5 }}
            className="absolute w-8 h-8 rounded-full bg-[#F57224] z-0"
          />
        </>
      )}

      <motion.button
        whileHover={{ scale: disabled ? 1 : 1.05 }}
        whileTap={{ scale: disabled ? 1 : 0.95 }}
        onClick={handleClick}
        disabled={disabled || isProcessing}
        title={isRecording ? 'Tap to stop' : 'Tap to speak'}
        className={`relative z-10 w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-300
          ${isRecording
            ? 'bg-[#F57224] text-white shadow-md shadow-[#F57224]/30'
            : isProcessing
            ? 'bg-[#1a1a1a] text-[#5a5a5a] cursor-wait'
            : 'bg-[#1a1a1a] text-[#9a9a9a] hover:text-[#F57224] hover:bg-white/[0.06]'}`}
      >
        <AnimatePresence mode="wait">
          {isProcessing ? (
            <motion.span key="spin" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <Loader2 size={15} className="animate-spin" />
            </motion.span>
          ) : isRecording ? (
            <motion.div
              key="stop"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0 }}
              className="w-2.5 h-2.5 bg-white rounded-sm"
            />
          ) : (
            <motion.span key="mic" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <Mic size={15} />
            </motion.span>
          )}
        </AnimatePresence>
      </motion.button>
    </div>
  )
}
