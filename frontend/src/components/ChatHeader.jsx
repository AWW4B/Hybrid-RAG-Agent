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
  turnsUsed, turnsMax, status, isPlaying, backendStatus, user
}) {
  const displayName = user?.name || user?.username || ''

  return (
    <div className="flex items-center gap-4 px-6 py-4 bg-[#1a0f00] border-b border-white/5 flex-shrink-0 z-10 shadow-[0_4px_20px_rgba(245,114,36,0.06)]">
      {/* Brand Monogram */}
      <div className="flex items-center gap-2 group cursor-pointer">
        <div className="w-8 h-8 rounded-lg bg-[#F57224] flex items-center justify-center flex-shrink-0 shadow-lg shadow-orange-900/10">
          <ShoppingBag size={16} className="text-[#1a0f00]" />
        </div>
        <span className="font-serif italic text-lg text-[#f5ede2] font-semibold tracking-tight">
          Assistant
        </span>
      </div>

      <div className="flex-1" />

      {/* User Chip — dynamically showing user name if available */}
      {displayName && (
        <motion.div 
          initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}
          whileHover={{ scale: 1.02 }}
          className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-white/5 border border-white/10 rounded-full"
        >
          <div className="w-1.5 h-1.5 rounded-full bg-[#ff8c42] animate-pulse" />
          <span className="text-[9px] font-bold text-[#c4a882] tracking-[0.2em] font-mono uppercase">
            {displayName}
          </span>
        </motion.div>
      )}

      {/* Backend Status / Identity */}
      <div className="flex items-center gap-4 ml-2">
        {isPlaying && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex-shrink-0">
            <AudioWaveform bars={4} color="var(--brand-fire)" className="h-4" />
          </motion.div>
        )}
        
        <div className="flex items-center gap-2">
           <div className={`w-2 h-2 rounded-full ${backendStatus === 'online' ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]' : 'bg-red-500'}`} />
           <span className="text-[10px] uppercase tracking-widest font-bold text-[#c4a882]">
             {backendStatus}
           </span>
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-1 flex-shrink-0 ml-4">
        {onToggleHistory && (
          <IconBtn id="btn-history" title="Merchant Ledger" onClick={onToggleHistory}>
            <History size={18} className="text-[#c4a882] hover:text-[#F57224] transition-colors" />
          </IconBtn>
        )}
        {onReset && (
          <IconBtn id="btn-new-chat" title="Renew Bargain" onClick={onReset}>
            <RotateCcw size={18} className="text-[#c4a882] hover:text-[#F57224] transition-colors" />
          </IconBtn>
        )}
        {onMinimize && (
          <IconBtn id="btn-minimize" title="Conceal" onClick={onMinimize}>
            <Minus size={18} className="text-[#c4a882] hover:text-[#f5ede2] transition-colors" />
          </IconBtn>
        )}
        {onClose && (
          <IconBtn id="btn-close" title="Dismiss" onClick={onClose}>
            <X size={18} className="text-red-900/60 hover:text-red-500 transition-colors" />
          </IconBtn>
        )}
      </div>
    </div>
  )
}
