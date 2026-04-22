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
  const { authState, authError, isLoading, isAdmin, user, token, login, logout } = useAuth()
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
      <div className="min-h-screen flex items-center justify-center bg-[#1a0f00]">
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
      <div className="relative h-screen w-screen overflow-hidden bg-[#1a0f00]">
        <FullPageChat backendStatus={backendStatus} token={token} user={user} />
        
        {/* Topbar Layout Overlay (Close/Admin) */}
        <div className="fixed top-2 right-4 z-50 flex items-center gap-2">
          {isAdmin && (
            <motion.button
              whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
              onClick={() => setMode('admin')}
              className="flex items-center gap-2 px-3 py-1.5 rounded-full
                         bg-[#2a1a08] border border-[#ff8c42]/20 text-xs text-[#ff8c42]"
            >
              <BarChart2 size={12} /> Admin
            </motion.button>
          )}

          <motion.button
            onClick={logout}
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            className="flex items-center gap-2 px-3 py-1.5 rounded-full
                       bg-[#2a1a08] border border-red-900/30 text-xs text-red-500 hover:text-red-400"
          >
            <LogOut size={12} /> Logout
          </motion.button>
          
          <motion.button
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            onClick={() => setMode('widget')}
            className="flex items-center gap-2 px-3 py-1.5 rounded-full
                       bg-[#3d2a14] border border-white/5 text-xs text-[#f5ede2]"
          >
            <Minimize2 size={12} /> Exit Full Chat
          </motion.button>
        </div>
      </div>
    )
  }

  // ── Widget mode (landing page + FAB) ─────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#1a0f00]">
      {/* Nav bar */}
      <header className="fixed top-0 left-0 right-0 z-40 bg-[#1a0f00]/60 backdrop-blur-xl border-b border-white/5 shadow-2xl">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, #F57224, #ff8c42)' }}>
            <ShoppingBag size={16} className="text-[#1a0f00]" />
          </div>
          <span className="font-serif italic text-lg text-[#f5ede2] font-semibold tracking-tight">Daraz Assistant</span>

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

          {/* Admin button — improved contrast for dark mode */}
          {isAdmin && (
            <motion.button
              id="open-admin-btn"
              whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
              onClick={() => setMode('admin')}
              className="flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium
                         text-[#F57224] border border-[#F57224]/30 bg-[#F57224]/5 hover:bg-[#F57224]/10 transition"
            >
              <BarChart2 size={14} /> Admin
            </motion.button>
          )}

          <motion.button
            onClick={logout}
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            className="flex items-center gap-2 px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest
                       text-red-500/80 hover:text-red-400 bg-red-500/5 hover:bg-red-500/10 transition border border-red-500/20"
          >
            <LogOut size={12} /> Logout
          </motion.button>
        </div>
      </header>

      {/* Hero section */}
      <main className="pt-14 relative flex flex-col items-center justify-center min-h-screen px-6 overflow-hidden">
        {/* Decorative Background Elements */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#F57224]/10 rounded-full hero-glow animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-[#ff8c42]/5 rounded-full hero-glow animate-pulse [animation-delay:1s]" />
        
        <div className="absolute top-[20%] right-[15%] opacity-20 floating-decorative animate-float">
          <div className="w-24 h-24 border-2 border-[#F57224]/30 rounded-full orbit-ring" />
        </div>
        <div className="absolute bottom-[20%] left-[10%] opacity-10 floating-decorative animate-float [animation-delay:2s]">
          <div className="w-16 h-16 border border-[#c4a882] rotate-45" />
        </div>

        <AnimatePresence>
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="text-center max-w-xl relative z-10"
          >
            <motion.div
              initial={{ scale: 0.8, rotate: -10 }} animate={{ scale: 1, rotate: 0 }}
              transition={{ type: "spring", stiffness: 200, damping: 20 }}
              className="w-24 h-24 rounded-[2rem] mx-auto mb-10 flex items-center justify-center shadow-2xl shadow-black/80 border border-white/5 relative"
              style={{ background: 'linear-gradient(135deg, #F57224, #ff8c42)' }}
            >
              <div className="absolute inset-0 rounded-[2rem] bg-white/10 blur-[1px]" />
              <ShoppingBag size={48} className="text-[#1a0f00] relative z-10" />
            </motion.div>
 
            <h1 className="text-6xl font-extrabold text-[#f5ede2] mb-6 font-serif italic tracking-tighter leading-[1.1]">
              Daraz <span className="shimmer-text">Voice</span> Assistant
            </h1>
            <p className="text-[#c4a882] text-xl font-medium mb-12 max-w-md mx-auto leading-relaxed">
              Your haute‑couture shopping guide. <br/>
              <span className="opacity-60 italic">Inquire elegantly — or just speak your mind.</span>
            </p>

            <div className="flex flex-wrap justify-center gap-3 mb-14">
              {[
                { icon: '🎙️', label: 'Voice Interaction' },
                { icon: '⚡', label: 'Real-time Search' },
                { icon: '🔒', label: 'Secure Access' },
                { icon: '🧠', label: 'Souk Identity' },
              ].map(({ icon, label }) => (
                <motion.span 
                  key={label}
                  whileHover={{ y: -2, backgroundColor: 'rgba(245, 114, 36, 0.1)' }}
                  className="flex items-center gap-2 px-5 py-2.5 bg-[#1e1005]/60 rounded-full shadow-lg backdrop-blur-md
                             border border-[#F57224]/10 text-[10px] text-[#f5ede2] font-bold tracking-[0.2em] uppercase transition-all">
                  <span className="text-sm">{icon}</span> {label}
                </motion.span>
              ))}
            </div>

            <motion.div 
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1 }}
              className="space-y-4"
            >
              <p className="text-[10px] font-mono uppercase tracking-[0.3em] text-[#c4a882]/40">
                👇 Begin your journey below
              </p>
              <motion.button
                whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                onClick={() => setMode('fullpage')}
                className="px-8 py-3 rounded-full bg-white/5 border border-white/10 text-[#f5ede2] text-xs font-bold uppercase tracking-[0.2em] hover:bg-white/10 transition-all"
              >
                Enter Immersive Consultation
              </motion.button>
            </motion.div>
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Floating chat widget */}
      <ChatWidget backendStatus={backendStatus} token={token} user={user} />
    </div>
  )
}
