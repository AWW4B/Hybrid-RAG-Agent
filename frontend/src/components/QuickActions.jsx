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
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => onSelect(`${emoji} ${label}`)}
          className="flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium
                     border border-gray-200 bg-white text-gray-600 shadow-sm
                     hover:border-[#F57224] hover:text-[#F57224] transition-colors"
        >
          <span>{emoji}</span>
          <span>{label}</span>
        </motion.button>
      ))}
    </motion.div>
  )
}
