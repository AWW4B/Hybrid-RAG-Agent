// =============================================================================
// src/hooks/useAuth.js
// JWT authentication state.
// Cookie is HttpOnly (set by backend) for browser security.
// The raw token is also stored in state so the WebSocket can use it as a
// query param (since WebSocket does not send cookies on some browsers).
// =============================================================================
import { useState, useEffect, useCallback } from 'react'
import { login as apiLogin, logout as apiLogout, refreshToken, healthCheck } from '../utils/api.js'

export default function useAuth() {
  // 'unknown' | 'authenticated' | 'unauthenticated'
  const [authState,  setAuthState]  = useState('unknown')
  const [authError,  setAuthError]  = useState(null)
  const [isLoading,  setIsLoading]  = useState(false)
  const [token,      setToken]      = useState(null)   // raw JWT for WS query param
  const [isAdmin,    setIsAdmin]    = useState(false)  // decoded from JWT payload

  // Decode admin flag from JWT without verifying signature (server always verifies)
  const _decodeAdmin = (jwt) => {
    try {
      const payload = JSON.parse(atob(jwt.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
      return !!payload.admin
    } catch { return false }
  }

  // Probe auth status on mount by hitting /health.
  useEffect(() => {
    let cancelled = false
    healthCheck()
      .then(() => { if (!cancelled) setAuthState('authenticated') })
      .catch((err) => {
        if (cancelled) return
        if (err?.status === 401) setAuthState('unauthenticated')
        else setAuthState('authenticated')   // backend offline — bypass login for demo
      })
    return () => { cancelled = true }
  }, [])

  const login = useCallback(async (username, password) => {
    setIsLoading(true)
    setAuthError(null)
    try {
      const data = await apiLogin(username, password)
      // data.access_token is also returned in the response body
      const jwt = data?.access_token || null
      setToken(jwt)
      setIsAdmin(jwt ? _decodeAdmin(jwt) : false)
      setAuthState('authenticated')
      return data
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
    setToken(null)
    setIsAdmin(false)
  }, [])

  const refresh = useCallback(async () => {
    try {
      await refreshToken()
    } catch {
      setAuthState('unauthenticated')
      setToken(null)
      setIsAdmin(false)
    }
  }, [])

  return { authState, authError, isLoading, token, isAdmin, login, logout: doLogout, refresh }
}
