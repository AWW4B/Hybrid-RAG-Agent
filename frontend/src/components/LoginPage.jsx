// =============================================================================
// src/components/LoginPage.jsx
// JWT authentication screen with Daraz branding
// =============================================================================
import { useState } from 'react'
import { motion } from 'framer-motion'
import { ShoppingBag, LogIn, Eye, EyeOff, Loader2 } from 'lucide-react'

export default function LoginPage({ onLogin, error, isLoading }) {
  const [username, setUsername]     = useState('')
  const [password, setPassword]     = useState('')
  const [showPwd, setShowPwd]       = useState(false)
  const [localErr, setLocalErr]     = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLocalErr('')
    if (!username.trim()) return setLocalErr('Username is required.')
    if (!password)        return setLocalErr('Password is required.')
    try {
      await onLogin(username.trim(), password)
    } catch { /* error shown via prop */ }
  }

  const displayError = localErr || error

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-orange-50 via-white to-orange-100 p-4">
      {/* Background decoration */}
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
        {/* Orange header band */}
        <div className="bg-gradient-to-r from-[#F57224] to-[#ff8c42] px-8 pt-8 pb-10 text-white text-center">
          <div className="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center mx-auto mb-4">
            <ShoppingBag size={32} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Daraz Assistant</h1>
          <p className="text-sm text-orange-100 mt-1">Your AI Shopping Guide</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-8 py-8 space-y-5">
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase mb-2">
              Username
            </label>
            <input
              id="login-username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={isLoading}
              placeholder="Enter your username"
              className="w-full px-4 py-3 rounded-xl bg-gray-50 border border-gray-200 text-sm
                         outline-none focus:ring-2 focus:ring-[#F57224] focus:border-transparent
                         disabled:opacity-50 transition"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase mb-2">
              Password
            </label>
            <div className="relative">
              <input
                id="login-password"
                type={showPwd ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                placeholder="Enter your password"
                className="w-full px-4 py-3 pr-12 rounded-xl bg-gray-50 border border-gray-200
                           text-sm outline-none focus:ring-2 focus:ring-[#F57224] focus:border-transparent
                           disabled:opacity-50 transition"
              />
              <button
                type="button"
                onClick={() => setShowPwd(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                tabIndex={-1}
              >
                {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Error */}
          {displayError && (
            <motion.p
              initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
              className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2"
            >
              {displayError}
            </motion.p>
          )}

          <motion.button
            id="login-submit"
            type="submit"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-xl
                       bg-[#F57224] hover:bg-[#e0621a] text-white font-semibold text-sm
                       shadow-md disabled:opacity-60 transition"
          >
            {isLoading
              ? <Loader2 size={18} className="animate-spin" />
              : <><LogIn size={18} /> Sign In</>
            }
          </motion.button>
        </form>

        <p className="text-center text-xs text-gray-400 pb-6 px-8">
          Protected by JWT authentication
        </p>
      </motion.div>
    </div>
  )
}
