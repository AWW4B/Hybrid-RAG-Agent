// =============================================================================
// src/App.jsx
// Root component — handles auth state, mode switching (widget / fullpage / admin)
// =============================================================================
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ShoppingBag, Maximize2, Minimize2, LogOut, BarChart2 } from 'lucide-react'
import useAuth from './hooks/useAuth.js'
import LoginPage from './components/LoginPage.jsx'
import ChatWidget from './components/ChatWidget.jsx'
import FullPageChat from './components/FullPageChat.jsx'
import AdminDashboard from './components/AdminDashboard.jsx'
import { healthCheck } from './utils/api.js'

export default function App() {
  const { authState, authError, isLoading, isAdmin, login, logout } = useAuth()
  const [mode, setMode]                   = useState('widget')    // 'widget' | 'fullpage' | 'admin'
  const [backendStatus, setBackendStatus] = useState('checking')  // 'checking' | 'online' | 'offline'

  // Poll backend health on mount
  useEffect(() => {
    healthCheck()
      .then(() => setBackendStatus('online'))
      .catch(() => setBackendStatus('offline'))
  }, [])

  // ── Loading spinner ──────────────────────────────────────────────────────
  if (authState === 'unknown') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#f5f5f5]">
        <div className="w-12 h-12 rounded-full border-4 border-[#F57224] border-t-transparent animate-spin" />
      </div>
    )
  }

  // ── Login / Register ─────────────────────────────────────────────────────
  if (authState === 'unauthenticated') {
    return <LoginPage onLogin={login} error={authError} isLoading={isLoading} />
  }

  // ── Admin Dashboard ──────────────────────────────────────────────────────
  if (mode === 'admin') {
    return <AdminDashboard onClose={() => setMode('widget')} />
  }

  // ── Full-page chat ────────────────────────────────────────────────────────
  if (mode === 'fullpage') {
    return (
      <div className="relative">
        <FullPageChat backendStatus={backendStatus} />
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2">
          <motion.button
            id="switch-widget-btn"
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            onClick={() => setMode('widget')}
            className="flex items-center gap-2 px-3 py-2 rounded-full
                       bg-white shadow-md text-sm text-gray-600 hover:text-[#F57224] border border-gray-200"
          >
            <Minimize2 size={14} /> Widget
          </motion.button>

          {isAdmin && (
            <motion.button
              whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
              onClick={() => setMode('admin')}
              className="flex items-center gap-2 px-3 py-2 rounded-full
                         bg-white shadow-md text-sm text-[#F57224] border border-orange-200"
            >
              <BarChart2 size={14} /> Admin
            </motion.button>
          )}

          <motion.button
            onClick={logout}
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            className="flex items-center gap-2 px-3 py-2 rounded-full
                       bg-white shadow-md text-sm text-red-600 hover:text-red-700 border border-red-100"
          >
            <LogOut size={14} /> Logout
          </motion.button>
        </div>
      </div>
    )
  }

  // ── Widget mode (landing page + FAB) ─────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#f5f5f5]">
      {/* Nav bar */}
      <header className="fixed top-0 left-0 right-0 z-40 bg-white border-b border-gray-100 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, #F57224, #ff8c42)' }}>
            <ShoppingBag size={16} className="text-white" />
          </div>
          <span className="font-bold text-gray-800">Daraz Assistant</span>

          {/* Backend status pill */}
          <div className="flex items-center gap-1.5 ml-2">
            <span className={`w-2 h-2 rounded-full ${
              backendStatus === 'online'  ? 'bg-green-400' :
              backendStatus === 'offline' ? 'bg-red-400'   : 'bg-yellow-400'
            }`} />
            <span className="text-xs text-gray-400 capitalize">{backendStatus}</span>
          </div>

          <div className="flex-1" />

          <motion.button
            id="open-fullchat-btn"
            whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
            onClick={() => setMode('fullpage')}
            className="flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium text-white shadow"
            style={{ background: 'linear-gradient(135deg, #F57224, #ff8c42)' }}
          >
            <Maximize2 size={14} /> Open Full Chat
          </motion.button>

          {/* Admin button — only for users with admin JWT claim */}
          {isAdmin && (
            <motion.button
              id="open-admin-btn"
              whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
              onClick={() => setMode('admin')}
              className="flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium
                         text-[#F57224] border border-orange-200 hover:bg-orange-50 transition"
            >
              <BarChart2 size={14} /> Admin
            </motion.button>
          )}

          <motion.button
            onClick={logout}
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            className="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium
                       text-red-600 hover:bg-red-50 transition border border-red-100"
          >
            <LogOut size={14} /> Logout
          </motion.button>
        </div>
      </header>

      {/* Hero section */}
      <main className="pt-14 flex flex-col items-center justify-center min-h-screen px-6">
        <AnimatePresence>
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center max-w-xl"
          >
            <motion.div
              initial={{ scale: 0.8 }} animate={{ scale: 1 }}
              className="w-24 h-24 rounded-3xl mx-auto mb-6 flex items-center justify-center shadow-2xl"
              style={{ background: 'linear-gradient(135deg, #F57224, #ff8c42)' }}
            >
              <ShoppingBag size={48} className="text-white" />
            </motion.div>

            <h1 className="text-4xl font-extrabold text-gray-800 mb-3">
              Daraz <span style={{ color: '#F57224' }}>Voice</span> Assistant
            </h1>
            <p className="text-gray-500 text-lg mb-8">
              Your AI‑powered shopping guide. Ask anything — or just talk to it!
            </p>

            <div className="flex flex-wrap justify-center gap-3 mb-8">
              {[
                { icon: '🎙️', label: 'Voice to Voice' },
                { icon: '⚡', label: 'Sub-second Latency' },
                { icon: '🔒', label: 'Private & Local' },
                { icon: '🧠', label: 'Remembers You' },
              ].map(({ icon, label }) => (
                <span key={label}
                  className="flex items-center gap-2 px-4 py-2 bg-white rounded-full shadow-sm
                             border border-gray-100 text-sm text-gray-600 font-medium">
                  {icon} {label}
                </span>
              ))}
            </div>

            <p className="text-sm text-gray-400">
              👇 Open the chat widget below, or click{' '}
              <button onClick={() => setMode('fullpage')} className="text-[#F57224] underline font-medium">
                Full Chat
              </button>{' '}
              for a larger experience.
            </p>
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Floating chat widget */}
      <ChatWidget backendStatus={backendStatus} />
    </div>
  )
}
