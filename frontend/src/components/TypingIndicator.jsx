// =============================================================================
// src/components/TypingIndicator.jsx
// 3-dot bounce animation shown while LLM is generating
// =============================================================================
import { motion } from 'framer-motion'

export default function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className="flex items-end gap-3 px-6 py-2"
    >
      <div className="px-5 py-3 rounded-2xl rounded-tl-none bg-[#3d2a14] border border-[#ff8c42]/10 flex items-center gap-1.5 glass-shadow">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            animate={{ 
              opacity: [0.3, 1, 0.3],
              scale: [1, 1.2, 1],
              backgroundColor: ['#3d2a14', '#F57224', '#3d2a14']
            }}
            transition={{
              duration: 1.2,
              repeat: Infinity,
              delay: i * 0.2,
              ease: "easeInOut"
            }}
            className="w-1.5 h-1.5 rounded-full shadow-[0_0_8px_rgba(245,114,36,0.3)]"
          />
        ))}
      </div>
      <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#c4a882] opacity-50 pb-2">
        Consulting the Merchant...
      </span>
    </motion.div>
  )
}
