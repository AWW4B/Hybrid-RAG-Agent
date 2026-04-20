// =============================================================================
// src/hooks/useAuth.js
// JWT authentication state. Cookie is HttpOnly (set by backend),
// so we infer auth status from /health response codes.
// =============================================================================
import { useState, useEffect, useCallback } from 'react'
import { login as apiLogin, logout as apiLogout, refreshToken, healthCheck } from '../utils/api.js'

export default function useAuth() {
  // 'unknown' | 'authenticated' | 'unauthenticated'
  const [authState, setAuthState] = useState('unknown')
  const [authError, setAuthError] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  // Probe auth status on mount by hitting /health.
  // If backend returns 401 we're unauthenticated; 200 means cookie is valid.
  // If backend is offline, we optimistically let the user in (loading state).
  useEffect(() => {
    let cancelled = false
    healthCheck()
      .then(() => { if (!cancelled) setAuthState('authenticated') })
      .catch((err) => {
        if (cancelled) return
        if (err?.status === 401) setAuthState('unauthenticated')
        else setAuthState('authenticated') // backend offline — bypass login for demo
      })
    return () => { cancelled = true }
  }, [])

  const login = useCallback(async (username, password) => {
    setIsLoading(true)
    setAuthError(null)
    try {
      await apiLogin(username, password)
      setAuthState('authenticated')
    } catch (err) {
      setAuthError(err.message || 'Login failed. Check your credentials.')
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const doLogout = useCallback(async () => {
    await apiLogout().catch(() => {})
    setAuthState('unauthenticated')
  }, [])

  const refresh = useCallback(async () => {
    try {
      await refreshToken()
    } catch {
      setAuthState('unauthenticated')
    }
  }, [])

  return { authState, authError, isLoading, login, logout: doLogout, refresh }
}
