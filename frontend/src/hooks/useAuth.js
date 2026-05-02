// =============================================================================
// src/hooks/useAuth.js
// Simple auth state — no JWT, no refresh tokens.
// Stores user_id + username in sessionStorage.
// =============================================================================
import { useState, useEffect, useCallback } from 'react'
import { login as apiLogin, logout as apiLogout } from '../utils/api.js'

export default function useAuth() {
  const [authState, setAuthState]  = useState('unknown')  // 'unknown' | 'authenticated' | 'unauthenticated'
  const [authError, setAuthError]  = useState(null)
  const [isLoading, setIsLoading]  = useState(false)
  const [user, setUser]            = useState(null)        // { user_id, username }
  const [isAdmin, setIsAdmin]      = useState(false)

  // Rehydrate from sessionStorage on mount
  useEffect(() => {
    const stored = sessionStorage.getItem('user')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        setUser(parsed)
        setIsAdmin(parsed.username === 'admin')
        setAuthState('authenticated')
      } catch {
        sessionStorage.removeItem('user')
        setAuthState('unauthenticated')
      }
    } else {
      setAuthState('unauthenticated')
    }
  }, [])

  const login = useCallback(async (username, password) => {
    setIsLoading(true)
    setAuthError(null)
    try {
      const data = await apiLogin(username, password)
      const userData = { user_id: data.user_id, username: data.username }
      setUser(userData)
      setIsAdmin(data.username === 'admin')
      sessionStorage.setItem('user', JSON.stringify(userData))
      setAuthState('authenticated')
      return data
    } catch (err) {
      setAuthError(err.message || 'Login failed.')
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const doLogout = useCallback(async () => {
    await apiLogout()
    sessionStorage.removeItem('user')
    setAuthState('unauthenticated')
    setUser(null)
    setIsAdmin(false)
  }, [])

  return { authState, authError, isLoading, user, isAdmin, login, logout: doLogout }
}
