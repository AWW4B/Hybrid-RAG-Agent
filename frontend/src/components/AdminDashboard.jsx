// =============================================================================
// src/components/AdminDashboard.jsx
// Simplified placeholder — backend only has GET /admin/dashboard
// =============================================================================
import { motion } from 'framer-motion'
import { X, BarChart2 } from 'lucide-react'

export default function AdminDashboard({ onClose }) {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-[#f0f0f0] flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center max-w-md p-8"
      >
        <div className="w-16 h-16 rounded-2xl mx-auto mb-6 flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg, #F57224, #ff6b35)' }}>
          <BarChart2 size={28} className="text-white" />
        </div>
        <h1 className="text-2xl font-bold mb-2">Admin Dashboard</h1>
        <p className="text-[#5a5a5a] mb-8">Admin features coming soon. The backend is focused on speed.</p>
        {onClose && (
          <button onClick={onClose}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl mx-auto text-sm font-medium
                       text-[#9a9a9a] hover:text-white border border-white/[0.08] hover:bg-white/[0.04] transition">
            <X size={14} /> Back to Chat
          </button>
        )}
      </motion.div>
    </div>
  )
}
