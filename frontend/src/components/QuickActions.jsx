// =============================================================================
// src/components/QuickActions.jsx
// Suggested query chips shown after the first welcome message
// =============================================================================
import { motion } from 'framer-motion'

const ACTIONS = [
  { label: 'Best Deals', emoji: '🔥' },
  { label: 'Phones',     emoji: '📱' },
  { label: 'Electronics',emoji: '🖥' },
  { label: 'Fashion',    emoji: '👕' },
  { label: 'Laptops',    emoji: '💻' },
]

export default function QuickActions({ onSelect }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      className="flex flex-wrap gap-2 px-4 pb-3"
    >
      {ACTIONS.map(({ label, emoji }) => (
        <motion.button
          key={label}
          id={`quick-${label.toLowerCase()}`}
          whileHover={{ scale: 1.05, backgroundColor: 'rgba(245, 114, 36, 0.1)' }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onSelect(`${emoji} ${label}`)}
          className="flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold
                     border border-[#ff8c42]/20 bg-[#2a1a08] text-[#c4a882] 
                     hover:border-[#F57224] hover:text-[#f5ede2] transition-all uppercase tracking-widest font-mono"
        >
          <span>{emoji}</span>
          <span>{label}</span>
        </motion.button>
      ))}
    </motion.div>
  )
}
