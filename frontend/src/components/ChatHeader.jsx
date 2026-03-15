// =============================================================================
// src/components/ChatHeader.jsx
// Orange gradient header with status, turn counter, and action buttons
// =============================================================================
import { motion } from 'framer-motion'
import { ShoppingBag, RotateCcw, History, Minus, X } from 'lucide-react'
import AudioWaveform from './AudioWaveform.jsx'

function IconBtn({ id, title, onClick, children }) {
  return (
    <motion.button
      id={id}
      title={title}
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.9 }}
      onClick={onClick}
      className="p-2 rounded-full hover:bg-white/20 text-white transition"
    >
      {children}
    </motion.button>
  )
}

export default function ChatHeader({
  onReset, onMinimize, onClose, onToggleHistory,
  turnsUsed, turnsMax, status, isPlaying, backendStatus
}) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-[#F57224] to-[#ff8c42] rounded-t-2xl flex-shrink-0">
      {/* Avatar */}
      <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center flex-shrink-0">
        <ShoppingBag size={20} className="text-white" />
      </div>

      {/* Title + status */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-white font-semibold text-sm truncate">Daraz Assistant</span>
          {/* Online indicator */}
          <div className="relative flex-shrink-0 flex items-center gap-1.5 ml-1">
            <span className={`w-2.5 h-2.5 rounded-full ${backendStatus === 'online' ? 'bg-green-400' : backendStatus === 'offline' ? 'bg-red-400' : 'bg-yellow-400'}`} />
            <span className="text-[10px] text-white/90 capitalize font-medium">{backendStatus === 'online' ? 'Backend Online' : backendStatus === 'offline' ? 'Backend Offline' : 'Connecting...'}</span>
          </div>
          {/* Playing waveform */}
          {isPlaying && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex-shrink-0">
              <AudioWaveform bars={4} color="white" className="h-3" />
            </motion.div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-orange-100 text-[10px]">
            {status === 'ended' ? '🔴 Session ended' : '🟢 Online'}
          </span>
          {turnsMax > 0 && (
            <span className="text-orange-200 text-[10px] bg-white/15 px-1.5 py-0.5 rounded-full">
              {turnsUsed}/{turnsMax} turns
            </span>
          )}
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-0.5 flex-shrink-0">
        {onToggleHistory && (
          <IconBtn id="btn-history" title="Chat history" onClick={onToggleHistory}>
            <History size={16} />
          </IconBtn>
        )}
        {onReset && (
          <IconBtn id="btn-new-chat" title="New chat" onClick={onReset}>
            <RotateCcw size={16} />
          </IconBtn>
        )}
        {onMinimize && (
          <IconBtn id="btn-minimize" title="Minimize" onClick={onMinimize}>
            <Minus size={16} />
          </IconBtn>
        )}
        {onClose && (
          <IconBtn id="btn-close" title="Close" onClick={onClose}>
            <X size={16} />
          </IconBtn>
        )}
      </div>
    </div>
  )
}
