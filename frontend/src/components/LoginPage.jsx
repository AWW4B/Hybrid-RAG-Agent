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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-orange-50 via-white to-orange-100 p-4">
      {/* Background blobs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-32 -right-32 w-96 h-96 rounded-full opacity-10"
          style={{ background: 'radial-gradient(circle, #F57224, transparent)' }} />
        <div className="absolute -bottom-32 -left-32 w-96 h-96 rounded-full opacity-10"
          style={{ background: 'radial-gradient(circle, #F57224, transparent)' }} />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 28 }}
        className="relative w-full max-w-sm bg-white rounded-3xl shadow-2xl overflow-hidden"
      >
        {/* Orange header */}
        <div className="bg-gradient-to-r from-[#F57224] to-[#ff8c42] px-8 pt-8 pb-10 text-white text-center">
          <div className="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center mx-auto mb-4">
            <ShoppingBag size={32} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Daraz Assistant</h1>
          <p className="text-sm text-orange-100 mt-1">Your AI Shopping Guide</p>
        </div>

        {/* Tab switcher */}
        <div className="flex border-b border-gray-100">
          {['login', 'register'].map((t) => (
            <button
              key={t}
              onClick={() => { setTab(t); setLocalErr(''); setRegOk(false) }}
              className={`flex-1 py-3 text-sm font-semibold transition-colors
                ${tab === t ? 'text-[#F57224] border-b-2 border-[#F57224]' : 'text-gray-400 hover:text-gray-600'}`}
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
              initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 12 }}
              onSubmit={handleLogin}
              className="px-8 py-6 space-y-4"
            >
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1.5">Username</label>
                <input id="login-username" type="text" autoComplete="username"
                  value={username} onChange={(e) => setUsername(e.target.value)} disabled={busy}
                  placeholder="Enter your username"
                  className="w-full px-4 py-3 rounded-xl bg-gray-50 border border-gray-200 text-sm
                             outline-none focus:ring-2 focus:ring-[#F57224] focus:border-transparent
                             disabled:opacity-50 transition" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1.5">Password</label>
                <div className="relative">
                  <input id="login-password" type={showPwd ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy}
                    placeholder="Enter your password"
                    className="w-full px-4 py-3 pr-12 rounded-xl bg-gray-50 border border-gray-200 text-sm
                               outline-none focus:ring-2 focus:ring-[#F57224] focus:border-transparent
                               disabled:opacity-50 transition" />
                  <button type="button" onClick={() => setShowPwd(v => !v)} tabIndex={-1}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600">
                    {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {displayError && (
                <motion.p initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
                  className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {displayError}
                </motion.p>
              )}

              <motion.button id="login-submit" type="submit"
                whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} disabled={busy}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-xl
                           bg-[#F57224] hover:bg-[#e0621a] text-white font-semibold text-sm
                           shadow-md disabled:opacity-60 transition">
                {busy ? <Loader2 size={18} className="animate-spin" /> : <><LogIn size={18} /> Sign In</>}
              </motion.button>
            </motion.form>

          ) : (
            <motion.form
              key="register"
              initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              onSubmit={handleRegister}
              className="px-8 py-6 space-y-4"
            >
              {regOk && (
                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2 flex items-center gap-2">
                  <CheckCircle2 size={14} /> Account created! Switching to login…
                </motion.p>
              )}

              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1.5">Username</label>
                <input id="reg-username" type="text" autoComplete="username"
                  value={username} onChange={(e) => setUsername(e.target.value)} disabled={busy}
                  placeholder="3–32 chars, letters/numbers/-/_"
                  className="w-full px-4 py-3 rounded-xl bg-gray-50 border border-gray-200 text-sm
                             outline-none focus:ring-2 focus:ring-[#F57224] disabled:opacity-50 transition" />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1.5">Email</label>
                <input id="reg-email" type="email" autoComplete="email"
                  value={email} onChange={(e) => setEmail(e.target.value)} disabled={busy}
                  placeholder="you@example.com"
                  className="w-full px-4 py-3 rounded-xl bg-gray-50 border border-gray-200 text-sm
                             outline-none focus:ring-2 focus:ring-[#F57224] disabled:opacity-50 transition" />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1.5">Password</label>
                <div className="relative">
                  <input id="reg-password" type={showPwd ? 'text' : 'password'}
                    autoComplete="new-password"
                    value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy}
                    placeholder="Min 8 chars"
                    className="w-full px-4 py-3 pr-12 rounded-xl bg-gray-50 border border-gray-200 text-sm
                               outline-none focus:ring-2 focus:ring-[#F57224] disabled:opacity-50 transition" />
                  <button type="button" onClick={() => setShowPwd(v => !v)} tabIndex={-1}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600">
                    {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <PasswordStrength password={password} />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1.5">Confirm Password</label>
                <input id="reg-confirm" type={showPwd ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={confirm} onChange={(e) => setConfirm(e.target.value)} disabled={busy}
                  placeholder="Repeat password"
                  className={`w-full px-4 py-3 rounded-xl bg-gray-50 border text-sm
                             outline-none focus:ring-2 focus:ring-[#F57224] disabled:opacity-50 transition
                             ${confirm && confirm !== password ? 'border-red-300' : 'border-gray-200'}`} />
                {confirm && confirm !== password && (
                  <p className="mt-1 text-xs text-red-500">Passwords do not match.</p>
                )}
              </div>

              {localErr && (
                <motion.p initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
                  className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {localErr}
                </motion.p>
              )}

              <motion.button id="register-submit" type="submit"
                whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} disabled={busy}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-xl
                           bg-[#F57224] hover:bg-[#e0621a] text-white font-semibold text-sm
                           shadow-md disabled:opacity-60 transition">
                {busy ? <Loader2 size={18} className="animate-spin" /> : <><UserPlus size={18} /> Create Account</>}
              </motion.button>
            </motion.form>
          )}
        </AnimatePresence>

        <p className="text-center text-xs text-gray-400 pb-5">Protected by JWT authentication</p>
      </motion.div>
    </div>
  )
}
