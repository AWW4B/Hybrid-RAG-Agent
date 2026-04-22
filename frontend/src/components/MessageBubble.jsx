// =============================================================================
// src/components/MessageBubble.jsx
// Single message row — user (right, orange) or bot (left, white)
// Supports streaming cursor, voice messages, error/cancelled states
// =============================================================================
import { Volume2 } from 'lucide-react'
import { motion } from 'framer-motion'
import AudioWaveform from './AudioWaveform.jsx'

function formatTime(iso) {
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
  catch { return '' }
}

export default function MessageBubble({ message, isPlaying, onStopSpeaking }) {
  const { role, content, timestamp, streaming, isError, cancelled, latency_ms, isVoice } = message
  const isUser = role === 'user'

  const hasProducts = content.includes('[PRODUCT')
  const products = hasProducts ? [
    { name: "Electronic Hub X1", price: "PKR 12,500", img: "https://images.unsplash.com/photo-1546435770-a3e426ca472b?w=200&q=80" },
    { name: "Vintage Merchant Watch", price: "PKR 8,900", img: "https://images.unsplash.com/photo-1524592094714-0f0654e20314?w=200&q=80" }
  ] : []

  return (
    <div className={`flex items-end gap-3 px-6 py-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div className={`max-w-[85%] flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`relative px-5 py-3.5 text-sm leading-relaxed whitespace-pre-wrap glass-shadow transition-all duration-300
                      ${isUser
                        ? 'bg-gradient-to-br from-[#F57224] to-[#ff8c42] text-[#1a0f00] rounded-[1.5rem] rounded-br-none font-bold'
                        : `bg-[#1e1005]/80 backdrop-blur-xl border border-white/5 text-[#f5ede2] rounded-[1.5rem] rounded-tl-none shadow-black/40 ${streaming ? 'border-l-4 border-l-[#F57224]' : 'border-l-[3px] border-l-[#F57224]/40'}`
                      }`}
        >
          {!isUser && (
            <div className={`absolute left-[-4px] top-4 bottom-4 w-[4px] bg-[#F57224] transition-all duration-500 rounded-full ${streaming ? 'blur-[2px] opacity-100 animate-breathing' : 'opacity-40 blur-none'}`} />
          )}

          {isVoice ? (
            <div className="flex items-center gap-3">
              <AudioWaveform bars={8} color="currentColor" className="h-4" />
              <span className="text-xs font-mono uppercase tracking-widest opacity-80">Vocal Ledger</span>
            </div>
          ) : (
            <span className="font-sans">
              {content.replace(/\[PRODUCT.*?\]/g, '')}
            </span>
          )}

          {streaming && (
            <motion.span 
              animate={{ opacity: [1, 0] }} transition={{ repeat: Infinity, duration: 0.6 }}
              className="inline-block w-1.5 h-4 bg-[#F57224] ml-2 align-middle rounded-full shadow-[0_0_12px_rgba(245,114,36,0.6)]" 
            />
          )}
        </div>

        {!isUser && products.length > 0 && (
          <div className="flex gap-4 overflow-x-auto w-full py-4 px-2 no-scrollbar">
            {products.map((p, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, scale: 0.9, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                whileHover={{ y: -4, scale: 1.02 }}
                transition={{ delay: 0.1 * idx, type: "spring", stiffness: 300, damping: 20 }}
                className="flex-shrink-0 w-64 bg-[#1e1005]/80 border border-white/10 rounded-3xl p-3 flex gap-4 glass-shadow relative overflow-hidden group"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent pointer-events-none" />
                <img src={p.img} alt={p.name} className="w-20 h-20 rounded-2xl object-cover shadow-lg relative z-10 group-hover:scale-105 transition-transform duration-500" />
                <div className="flex flex-col justify-center gap-1.5 relative z-10 flex-1">
                  <span className="text-xs font-bold text-[#f5ede2] line-clamp-1 tracking-tight">{p.name}</span>
                  <span className="text-[10px] font-bold text-[#F57224] font-mono tracking-tighter">{p.price}</span>
                  <motion.span 
                    whileHover={{ x: 3 }}
                    className="text-[9px] font-black text-[#c4a882] uppercase tracking-widest cursor-pointer mt-1 flex items-center gap-1"
                  >
                    Explore <span className="opacity-40">→</span>
                  </motion.span>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        <div className={`flex items-center gap-3 px-1 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
          <span className="text-[10px] font-mono text-[#c4a882] opacity-50 uppercase tracking-tighter">
            {formatTime(timestamp)}
            {latency_ms && <span> · {(latency_ms / 1000).toFixed(1)}s</span>}
          </span>

          {!isUser && !streaming && !isError && (
            <motion.div 
               whileHover={{ scale: 1.05 }}
               className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#3d2a14] border border-white/5"
            >
              <Volume2 size={10} className="text-[#F57224]" />
              <span className="text-[9px] font-bold text-[#c4a882] uppercase tracking-widest">
                {isPlaying ? 'Speaking' : 'Vocalized'}
              </span>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  )
}
