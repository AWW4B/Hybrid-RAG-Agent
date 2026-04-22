// =============================================================================
// src/components/LoginPage.jsx
// JWT auth screen with login + register tabs, password strength indicator.
// =============================================================================
import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ShoppingBag, LogIn, UserPlus, Eye, EyeOff, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { register as apiRegister } from '../utils/api.js'

// ---------------------------------------------------------------------------
// Password strength rules (mirrors server-side validate_password)
// ---------------------------------------------------------------------------
const RULES = [
  { id: 'len',   label: 'At least 8 characters',      test: (p) => p.length >= 8 },
  { id: 'upper', label: 'One uppercase letter (A-Z)',  test: (p) => /[A-Z]/.test(p) },
  { id: 'lower', label: 'One lowercase letter (a-z)',  test: (p) => /[a-z]/.test(p) },
  { id: 'digit', label: 'One digit (0-9)',             test: (p) => /\d/.test(p) },
  {
    id: 'bytes',
    label: 'Under 72 bytes (watch emoji/special chars)',
    test: (p) => new TextEncoder().encode(p).length <= 72,
  },
]

function PasswordStrength({ password }) {
  const results = useMemo(() => RULES.map((r) => ({ ...r, ok: r.test(password) })), [password])
  if (!password) return null
  return (
    <ul className="mt-2 space-y-1">
      {results.map((r) => (
        <li key={r.id} className="flex items-center gap-1.5 text-xs">
          {r.ok
            ? <CheckCircle2 size={12} className="text-green-500 shrink-0" />
            : <XCircle      size={12} className="text-red-400 shrink-0" />}
          <span className={r.ok ? 'text-green-600' : 'text-red-400'}>{r.label}</span>
        </li>
      ))}
    </ul>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function LoginPage({ onLogin, error, isLoading }) {
  const [tab, setTab]           = useState('login')     // 'login' | 'register'
  const [username, setUsername] = useState('')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [confirm,  setConfirm]  = useState('')
  const [showPwd,  setShowPwd]  = useState(false)
  const [localErr, setLocalErr] = useState('')
  const [regOk,    setRegOk]    = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const displayError = localErr || (tab === 'login' ? error : null)

  // ---- Login ----
  const handleLogin = async (e) => {
    e.preventDefault()
    setLocalErr('')
    if (!username.trim()) return setLocalErr('Username is required.')
    if (!password)        return setLocalErr('Password is required.')
    try {
      await onLogin(username.trim(), password)
    } catch { /* error shown via prop */ }
  }

  // ---- Register ----
  const handleRegister = async (e) => {
    e.preventDefault()
    setLocalErr('')
    if (!username.trim()) return setLocalErr('Username is required.')
    if (!email.trim())    return setLocalErr('Email is required.')
    if (!password)        return setLocalErr('Password is required.')
    if (password !== confirm) return setLocalErr('Passwords do not match.')
    const failing = RULES.filter((r) => !r.test(password))
    if (failing.length) return setLocalErr(failing[0].label)

    setSubmitting(true)
    try {
      await apiRegister(username.trim(), email.trim(), password)
      setRegOk(true)
      setLocalErr('')
      // Auto-switch to login after 1.5 s
      setTimeout(() => { setTab('login'); setRegOk(false) }, 1500)
    } catch (err) {
      const detail = err?.message || 'Registration failed.'
      setLocalErr(detail)
    } finally {
      setSubmitting(false)
    }
  }

  const busy = isLoading || submitting

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#1a0f00] p-4 relative">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 28 }}
        className="relative w-full max-w-sm bg-[#2a1a08] rounded-[2rem] shadow-2xl overflow-hidden glass-card glass-shadow"
      >
        {/* Boutique Header */}
        <div className="bg-gradient-to-br from-[#F57224] to-[#ff8c42] p-8 text-[#1a0f00] text-center">
          <div className="w-16 h-16 rounded-2xl bg-[#1a0f00]/10 backdrop-blur-sm flex items-center justify-center mx-auto mb-4">
            <ShoppingBag size={32} className="text-[#1a0f00]" />
          </div>
          <h1 className="text-3xl font-serif italic italic-size-144 font-bold tracking-tight">Daraz Assistant</h1>
          <p className="text-xs uppercase tracking-[0.2em] font-bold opacity-70 mt-1 mb-2">Haute Couture Insight</p>
        </div>

        {/* Tab switcher */}
        <div className="flex border-b border-white/5 bg-[#1a0f00]/30 backdrop-blur-md">
          {['login', 'register'].map((t) => (
            <button
              key={t}
              onClick={() => { setTab(t); setLocalErr(''); setRegOk(false) }}
              className={`flex-1 py-4 text-[10px] font-bold tracking-[0.2em] uppercase transition-all
                ${tab === t ? 'text-[#F57224] border-b-2 border-[#F57224] bg-[#F57224]/5' : 'text-[#c4a882] hover:text-[#f5ede2]'}`}
            >
              {t === 'login' ? 'Sign In' : 'Register'}
            </button>
          ))}
        </div>

        {/* Forms */}
        <AnimatePresence mode="wait">
          {tab === 'login' ? (
            <motion.form
              key="login"
              initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              onSubmit={handleLogin}
              className="px-8 py-8 space-y-5"
            >
              <div className="space-y-1.5">
                <label className="block text-[10px] font-bold text-[#c4a882] uppercase tracking-widest pl-1">Username</label>
                <input id="login-username" type="text" autoComplete="username"
                  value={username} onChange={(e) => setUsername(e.target.value)} disabled={busy}
                  placeholder="The chronicle name"
                  className="w-full px-4 py-3 rounded-xl bg-[#1a0f00] border border-white/5 text-sm text-[#f5ede2]
                             outline-none focus:ring-[3px] focus:ring-[#F57224]/15 focus:border-[#F57224]
                             disabled:opacity-50 transition-all placeholder-[#c4a882]/20" />
              </div>
              <div className="space-y-1.5">
                <label className="block text-[10px] font-bold text-[#c4a882] uppercase tracking-widest pl-1">Secret Key</label>
                <div className="relative">
                  <input id="login-password" type={showPwd ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy}
                    placeholder="The forbidden script"
                    className="w-full px-4 py-3 pr-12 rounded-xl bg-[#1a0f00] border border-white/5 text-sm text-[#f5ede2]
                               outline-none focus:ring-[3px] focus:ring-[#F57224]/15 focus:border-[#F57224]
                               disabled:opacity-50 transition-all placeholder-[#c4a882]/20" />
                  <button type="button" onClick={() => setShowPwd(v => !v)} tabIndex={-1}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-[#c4a882] hover:text-[#F57224] transition-colors">
                    {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {displayError && (
                <motion.p initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
                  className="text-[11px] font-medium text-red-500 bg-red-950/20 border border-red-900/30 rounded-xl px-4 py-3">
                  ⚠️ {displayError}
                </motion.p>
              )}

              <motion.button id="login-submit" type="submit"
                whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} disabled={busy}
                className="w-full flex items-center justify-center gap-3 py-3.5 rounded-xl
                           bg-gradient-to-r from-[#F57224] to-[#ff8c42] text-[#1a0f00] font-bold text-xs uppercase tracking-widest
                           shadow-xl shadow-orange-900/20 disabled:opacity-40 transition-all mt-4">
                {busy ? <Loader2 size={18} className="animate-spin" /> : <><LogIn size={18} /> Enter the Souk</>}
              </motion.button>
            </motion.form>

          ) : (
            <motion.form
              key="register"
              initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              onSubmit={handleRegister}
              className="px-8 py-8 space-y-5"
            >
              {regOk && (
                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="text-[11px] font-medium text-green-500 bg-green-950/20 border border-green-900/30 rounded-xl px-4 py-3 flex items-center gap-2">
                  <CheckCircle2 size={14} /> Ledger Record Created.
                </motion.p>
              )}

              <div className="space-y-1.5">
                <label className="block text-[10px] font-bold text-[#c4a882] uppercase tracking-widest pl-1">Handle</label>
                <input id="reg-username" type="text" autoComplete="username"
                  value={username} onChange={(e) => setUsername(e.target.value)} disabled={busy}
                  className="w-full px-4 py-3 rounded-xl bg-[#1a0f00] border border-white/5 text-sm text-[#f5ede2]
                             outline-none focus:ring-[3px] focus:ring-[#F57224]/15 disabled:opacity-50 transition-all font-sans" />
              </div>

              <div className="space-y-1.5">
                <label className="block text-[10px] font-bold text-[#c4a882] uppercase tracking-widest pl-1">Scroll Address</label>
                <input id="reg-email" type="email" autoComplete="email"
                  value={email} onChange={(e) => setEmail(e.target.value)} disabled={busy}
                  className="w-full px-4 py-3 rounded-xl bg-[#1a0f00] border border-white/5 text-sm text-[#f5ede2]
                             outline-none focus:ring-[3px] focus:ring-[#F57224]/15 disabled:opacity-50 transition-all font-sans" />
              </div>

              <div className="space-y-1.5">
                <label className="block text-[10px] font-bold text-[#c4a882] uppercase tracking-widest pl-1">Secret Key</label>
                <div className="relative">
                  <input id="reg-password" type={showPwd ? 'text' : 'password'}
                    autoComplete="new-password"
                    value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy}
                    className="w-full px-4 py-3 pr-12 rounded-xl bg-[#1a0f00] border border-white/5 text-sm text-[#f5ede2]
                               outline-none focus:ring-[3px] focus:ring-[#F57224]/15 disabled:opacity-50 transition-all" />
                  <button type="button" onClick={() => setShowPwd(v => !v)} tabIndex={-1}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-[#c4a882] hover:text-[#F57224] transition-colors">
                    {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <PasswordStrength password={password} />
              </div>

              <div className="space-y-1.5">
                <label className="block text-[10px] font-bold text-[#c4a882] uppercase tracking-widest pl-1">Confirm Secret Key</label>
                <input id="reg-confirm" type={showPwd ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={confirm} onChange={(e) => setConfirm(e.target.value)} disabled={busy}
                  className="w-full px-4 py-3 rounded-xl bg-[#1a0f00] border border-white/5 text-sm text-[#f5ede2]
                             outline-none focus:ring-[3px] focus:ring-[#F57224]/15 disabled:opacity-50 transition-all" />
              </div>

              {localErr && (
                <motion.p initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
                  className="text-[11px] font-medium text-red-500 bg-red-950/20 border border-red-900/30 rounded-xl px-4 py-3">
                  ⚠️ {localErr}
                </motion.p>
              )}

              <motion.button id="register-submit" type="submit"
                whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} disabled={busy}
                className="w-full flex items-center justify-center gap-3 py-3.5 rounded-xl
                           bg-gradient-to-r from-[#F57224] to-[#ff8c42] text-[#1a0f00] font-bold text-xs uppercase tracking-widest
                           shadow-xl shadow-orange-900/20 disabled:opacity-40 transition-all mt-4">
                {busy ? <Loader2 size={18} className="animate-spin" /> : <><UserPlus size={18} /> Inscribe Account</>}
              </motion.button>
            </motion.form>
          )}
        </AnimatePresence>

        <p className="text-center text-[9px] font-bold tracking-[0.2em] uppercase text-[#c4a882] opacity-30 pb-5">
          Secured via Merchant Cryptography
        </p>
      </motion.div>
    </div>
  )
}
