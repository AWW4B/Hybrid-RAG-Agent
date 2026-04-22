// =============================================================================
// src/components/VoiceMicButton.jsx
// Recording state machine button with animated pulse rings
// States: idle | requesting | recording | processing
// =============================================================================
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, Loader2 } from 'lucide-react'
import AudioWaveform from './AudioWaveform.jsx'

export default function VoiceMicButton({ micState, onStart, onStop, disabled }) {
  const isRecording    = micState === 'recording'
  const isRequesting   = micState === 'requesting'
  const isProcessing   = micState === 'processing'
  const isIdle         = micState === 'idle'

  const handleClick = () => {
    if (disabled) return
    if (isIdle || isRequesting) onStart?.()
    else if (isRecording)        onStop?.()
  }

  return (
    <div className="relative flex items-center justify-center">
      {/* Pulse rings — ember during recording */}
      {isRecording && (
        <>
          <motion.div 
            animate={{ scale: [1, 1.8], opacity: [0.5, 0] }}
            transition={{ repeat: Infinity, duration: 2 }}
            className="absolute w-8 h-8 rounded-full bg-[#ff8c42] z-0" 
          />
          <motion.div 
            animate={{ scale: [1, 1.4], opacity: [0.3, 0] }}
            transition={{ repeat: Infinity, duration: 1.5, delay: 0.5 }}
            className="absolute w-8 h-8 rounded-full bg-[#ff8c42] z-0" 
          />
        </>
      )}

      <motion.button
        id={`mic-btn-${micState}`}
        whileHover={{ scale: disabled ? 1 : 1.05 }}
        whileTap={{ scale: disabled ? 1 : 0.95 }}
        onClick={handleClick}
        disabled={disabled || isProcessing}
        className={`relative z-10 w-10 h-10 rounded-full flex items-center justify-center transition-all duration-500
                    ${isRecording  ? 'bg-[#ff8c42] text-[#1a0f00] shadow-[0_0_20px_rgba(255,140,66,0.4)]'
                    : isProcessing ? 'bg-[#3d2a14] text-[#c4a882] cursor-wait border border-white/5'
                    : 'bg-transparent text-[#c4a882] hover:text-[#F57224] hover:bg-white/5'}`}
      >
        <AnimatePresence mode="wait">
          {isProcessing ? (
            <motion.span key="spin" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <Loader2 size={18} className="animate-spin" />
            </motion.span>
          ) : isRecording ? (
            <motion.div key="stop" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} className="w-3 h-3 bg-[#1a0f00] rounded-sm" />
          ) : (
            <motion.span key="mic" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <Mic size={18} />
            </motion.span>
          )}
        </AnimatePresence>
      </motion.button>
    </div>
  )
}
