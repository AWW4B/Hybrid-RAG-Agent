// =============================================================================
// src/components/QuickActions.jsx
// Suggested query chips shown after the first welcome message
// =============================================================================
import { motion } from 'framer-motion'

const ACTIONS = [
  { label: 'Best Deals', emoji: '🔥' },
  { label: 'Phones',     emoji: '📱' },
  { label: 'Electronics', emoji: '🖥' },
  { label: 'Fashion',    emoji: '👕' },
  { label: 'Laptops',    emoji: '💻' },
]

export default function QuickActions({ onSelect }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="flex flex-wrap gap-2 px-2"
    >
      {ACTIONS.map(({ label, emoji }) => (
        <motion.button
          key={label}
          whileHover={{ scale: 1.03, backgroundColor: 'rgba(245, 114, 36, 0.08)' }}
          whileTap={{ scale: 0.97 }}
          onClick={() => onSelect(`Show me ${label.toLowerCase()}`)}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium
                     border border-white/[0.08] bg-[#141414] text-[#9a9a9a]
                     hover:border-[#F57224]/30 hover:text-[#f0f0f0] transition-all"
        >
          <span>{emoji}</span>
          <span>{label}</span>
        </motion.button>
      ))}
    </motion.div>
  )
}
