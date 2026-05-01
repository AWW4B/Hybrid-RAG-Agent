// =============================================================================
// src/components/LoginPage.jsx
// Clean, modern login/register — no ornate language, simple validation.
// =============================================================================
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ShoppingBag, LogIn, UserPlus, Eye, EyeOff, Loader2 } from 'lucide-react'
import { register as apiRegister } from '../utils/api.js'

export default function LoginPage({ onLogin, error, isLoading }) {
  const [tab, setTab]           = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd]   = useState(false)
  const [localErr, setLocalErr] = useState('')
  const [regOk, setRegOk]       = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const displayError = localErr || (tab === 'login' ? error : null)

  const handleLogin = async (e) => {
    e.preventDefault()
    setLocalErr('')
    if (!username.trim()) return setLocalErr('Username is required.')
    if (!password) return setLocalErr('Password is required.')
    try {
      await onLogin(username.trim(), password)
    } catch { /* error via prop */ }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    setLocalErr('')
    if (!username.trim()) return setLocalErr('Username is required.')
    if (!password) return setLocalErr('Password is required.')
    if (password.length > 20) return setLocalErr('Password must be 20 characters or fewer.')

    setSubmitting(true)
    try {
      await apiRegister(username.trim(), password)
      setRegOk(true)
      setLocalErr('')
      setTimeout(() => { setTab('login'); setRegOk(false) }, 1500)
    } catch (err) {
      setLocalErr(err?.message || 'Registration failed.')
    } finally {
      setSubmitting(false)
    }
  }

  const busy = isLoading || submitting

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a] p-4">
      {/* Subtle background glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/3 w-[500px] h-[500px] bg-[#F57224]/[0.04] rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/3 w-[400px] h-[400px] bg-[#ff6b35]/[0.03] rounded-full blur-[100px]" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: 'spring', stiffness: 300, damping: 28 }}
        className="relative w-full max-w-sm z-10"
      >
        {/* Header */}
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0.8 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 20 }}
            className="w-16 h-16 rounded-2xl mx-auto mb-5 flex items-center justify-center shadow-xl shadow-[#F57224]/10"
            style={{ background: 'linear-gradient(135deg, #F57224, #ff6b35)' }}
          >
            <ShoppingBag size={28} className="text-white" />
          </motion.div>
          <h1 className="text-2xl font-bold text-[#f0f0f0] tracking-tight">Daraz AI Assistant</h1>
          <p className="text-sm text-[#5a5a5a] mt-1">Your smart shopping companion</p>
        </div>

        {/* Card */}
        <div className="bg-[#111111] rounded-2xl border border-white/[0.06] overflow-hidden shadow-2xl shadow-black/40">
          {/* Tabs */}
          <div className="flex border-b border-white/[0.06]">
            {['login', 'register'].map((t) => (
              <button
                key={t}
                onClick={() => { setTab(t); setLocalErr(''); setRegOk(false) }}
                className={`flex-1 py-3.5 text-xs font-semibold uppercase tracking-wider transition-all
                  ${tab === t
                    ? 'text-[#F57224] border-b-2 border-[#F57224] bg-[#F57224]/[0.03]'
                    : 'text-[#5a5a5a] hover:text-[#9a9a9a]'}`}
              >
                {t === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>

          {/* Forms */}
          <AnimatePresence mode="wait">
            <motion.form
              key={tab}
              initial={{ opacity: 0, x: tab === 'login' ? -10 : 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: tab === 'login' ? 10 : -10 }}
              onSubmit={tab === 'login' ? handleLogin : handleRegister}
              className="p-6 space-y-4"
            >
              {regOk && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="text-xs text-emerald-400 bg-emerald-500/[0.08] border border-emerald-500/20 rounded-xl px-4 py-3 flex items-center gap-2">
                  ✓ Account created! Redirecting to sign in...
                </motion.div>
              )}

              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-[#9a9a9a]">Username</label>
                <input
                  type="text" autoComplete="username"
                  value={username} onChange={(e) => setUsername(e.target.value)} disabled={busy}
                  placeholder="Enter username"
                  className="w-full px-4 py-3 rounded-xl bg-[#1a1a1a] border border-white/[0.08] text-sm text-[#f0f0f0]
                             outline-none focus:ring-2 focus:ring-[#F57224]/20 focus:border-[#F57224]/40
                             disabled:opacity-50 transition placeholder-[#5a5a5a]"
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-[#9a9a9a]">Password</label>
                <div className="relative">
                  <input
                    type={showPwd ? 'text' : 'password'}
                    autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
                    value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy}
                    placeholder="Enter password"
                    className="w-full px-4 py-3 pr-12 rounded-xl bg-[#1a1a1a] border border-white/[0.08] text-sm text-[#f0f0f0]
                               outline-none focus:ring-2 focus:ring-[#F57224]/20 focus:border-[#F57224]/40
                               disabled:opacity-50 transition placeholder-[#5a5a5a]"
                  />
                  <button type="button" onClick={() => setShowPwd(v => !v)} tabIndex={-1}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-[#5a5a5a] hover:text-[#9a9a9a] transition">
                    {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                {tab === 'register' && (
                  <p className="text-[10px] text-[#5a5a5a] mt-1">Max 20 characters</p>
                )}
              </div>

              {displayError && (
                <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                  className="text-xs text-red-400 bg-red-500/[0.08] border border-red-500/20 rounded-xl px-4 py-3">
                  {displayError}
                </motion.p>
              )}

              <motion.button
                type="submit"
                whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}
                disabled={busy}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-sm
                           text-white shadow-lg shadow-[#F57224]/20 disabled:opacity-40 transition-all mt-2"
                style={{ background: 'linear-gradient(135deg, #F57224, #ff6b35)' }}
              >
                {busy
                  ? <Loader2 size={16} className="animate-spin" />
                  : tab === 'login'
                    ? <><LogIn size={16} /> Sign In</>
                    : <><UserPlus size={16} /> Create Account</>
                }
              </motion.button>
            </motion.form>
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  )
}
