// =============================================================================
// src/components/MessageBubble.jsx
// Clean message bubble — user (right, gradient) and assistant (left, surface)
// =============================================================================
import { motion } from 'framer-motion'

function formatTime(iso) {
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
  catch { return '' }
}

export default function MessageBubble({ message, isLast }) {
  const { role, content, timestamp, streaming, latency_ms } = message
  const isUser = role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} px-2 py-1`}>
      <div className={`max-w-[80%] flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Bubble */}
        <div className={`relative px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap transition-all
          ${isUser
            ? 'bg-gradient-to-br from-[#F57224] to-[#ff6b35] text-white rounded-2xl rounded-br-sm font-medium'
            : `bg-[#141414] border border-white/[0.06] text-[#e0e0e0] rounded-2xl rounded-tl-sm
               ${streaming ? 'border-l-2 border-l-[#F57224]' : ''}`
          }`}
        >
          <span>{content}</span>

          {streaming && (
            <motion.span
              animate={{ opacity: [1, 0] }}
              transition={{ repeat: Infinity, duration: 0.5 }}
              className="inline-block w-1.5 h-4 bg-[#F57224] ml-1 align-middle rounded-sm"
            />
          )}
        </div>

        {/* Timestamp + latency */}
        <div className={`flex items-center gap-2 px-1 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
          <span className="text-[10px] font-mono text-[#5a5a5a]">
            {formatTime(timestamp)}
            {latency_ms && <span> · {(latency_ms / 1000).toFixed(1)}s</span>}
          </span>
        </div>
      </div>
    </div>
  )
}
