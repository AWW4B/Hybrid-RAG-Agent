// =============================================================================
// src/components/ToolIndicator.jsx
// Shows which tools are being called, displayed below the input bar
// =============================================================================
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Zap, Truck, Calculator, GitCompare, BookOpen, Loader2, CheckCircle2 } from 'lucide-react'

const TOOL_ICONS = {
  'Product Search': Search,
  'Flash Deals': Zap,
  'Shipping': Truck,
  'Calculator': Calculator,
  'Comparison': GitCompare,
  'Knowledge Base': BookOpen,
}

export default function ToolIndicator({ toolStatus }) {
  if (!toolStatus) return null

  const isRunning = toolStatus.status === 'running'
  const isDone = toolStatus.status === 'done'

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 6, height: 0 }}
        animate={{ opacity: 1, y: 0, height: 'auto' }}
        exit={{ opacity: 0, y: 6, height: 0 }}
        transition={{ duration: 0.2 }}
        className="mt-2"
      >
        <div className={`
          flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium
          border transition-all duration-300
          ${isRunning
            ? 'bg-[#F57224]/[0.06] border-[#F57224]/20 text-[#F57224]'
            : 'bg-emerald-500/[0.06] border-emerald-500/20 text-emerald-400'
          }
        `}>
          {isRunning ? (
            <>
              <Loader2 size={13} className="animate-spin flex-shrink-0" />
              <span>{toolStatus.name || 'Processing...'}</span>
            </>
          ) : isDone && toolStatus.tools_used?.length > 0 ? (
            <>
              <CheckCircle2 size={13} className="flex-shrink-0" />
              <span className="flex items-center gap-1.5 flex-wrap">
                {toolStatus.tools_used.map((tool) => {
                  const Icon = TOOL_ICONS[tool] || BookOpen
                  return (
                    <span key={tool} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md
                      bg-white/[0.04] border border-white/[0.06]">
                      <Icon size={10} />
                      {tool}
                    </span>
                  )
                })}
              </span>
            </>
          ) : null}
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
