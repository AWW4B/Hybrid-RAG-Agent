// =============================================================================
// src/components/TypingIndicator.jsx
// 3-dot animation shown while LLM is generating
// =============================================================================
import { motion } from 'framer-motion'

export default function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 6 }}
      className="flex items-center gap-3 px-4 py-2"
    >
      <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-[#141414] border border-white/[0.06] flex items-center gap-1.5">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            animate={{
              opacity: [0.3, 1, 0.3],
              scale: [1, 1.2, 1],
            }}
            transition={{
              duration: 1,
              repeat: Infinity,
              delay: i * 0.15,
              ease: 'easeInOut',
            }}
            className="w-1.5 h-1.5 rounded-full bg-[#F57224]"
          />
        ))}
      </div>
      <span className="text-[10px] text-[#5a5a5a]">Thinking...</span>
    </motion.div>
  )
}
