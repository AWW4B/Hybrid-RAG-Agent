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
      {/* Floating badge above button */}
      <AnimatePresence>
        {(isRecording || isProcessing) && (
          <motion.div
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 6 }}
            className={`absolute bottom-full mb-2 left-1/2 -translate-x-1/2 whitespace-nowrap
                        text-[10px] font-semibold px-2 py-1 rounded-full shadow
                        ${isRecording ? 'bg-red-500 text-white' : 'bg-gray-700 text-white'}`}
          >
            {isRecording ? '● Recording' : 'Processing…'}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Pulse rings — only during recording */}
      {isRecording && (
        <>
          <span className="mic-pulse-ring absolute w-9 h-9 rounded-full bg-red-400 opacity-60" />
          <span className="mic-pulse-ring absolute w-9 h-9 rounded-full bg-red-400 opacity-40" />
        </>
      )}

      <motion.button
        id={`mic-btn-${micState}`}
        whileHover={{ scale: disabled ? 1 : 1.1 }}
        whileTap={{ scale: disabled ? 1 : 0.9 }}
        onClick={handleClick}
        disabled={disabled || isProcessing}
        className={`relative z-10 w-9 h-9 rounded-full flex items-center justify-center
                    transition-colors shadow-sm
                    ${isRecording  ? 'bg-red-500 text-white'
                    : isProcessing ? 'bg-gray-700 text-white cursor-wait'
                    : isRequesting ? 'bg-orange-100 text-[#F57224] opacity-70'
                    : 'bg-orange-50 text-[#F57224] hover:bg-orange-100'}`}
      >
        <AnimatePresence mode="wait">
          {isProcessing ? (
            <motion.span key="spin" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <Loader2 size={16} className="animate-spin" />
            </motion.span>
          ) : isRecording ? (
            <motion.span key="wave" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <AudioWaveform bars={4} className="h-4" color="white" />
            </motion.span>
          ) : (
            <motion.span key="mic" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <Mic size={16} />
            </motion.span>
          )}
        </AnimatePresence>
      </motion.button>
    </div>
  )
}
