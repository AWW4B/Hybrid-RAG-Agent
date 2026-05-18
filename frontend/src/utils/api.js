// =============================================================================
// src/utils/api.js
// All HTTP and WebSocket helpers — matched to new barebones backend
// =============================================================================

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
const WS_BASE  = import.meta.env.VITE_WS_BASE_URL  ||
  (window.location.protocol === 'https:' ? 'wss:' : 'ws:') +
  '//' + window.location.host

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
async function jsonFetch(path, options = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw Object.assign(new Error(err.detail || 'Request failed'), { status: res.status })
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
export async function login(username, password) {
  return jsonFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export async function register(username, password, email = '') {
  return jsonFetch('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password, email }),
  })
}

export async function logout() {
  return jsonFetch('/auth/logout', { method: 'POST' }).catch(() => {})
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------
export async function healthCheck() {
  return jsonFetch('/health')
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------
export async function createSession(userId, title = '') {
  return jsonFetch('/sessions/create', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, title }),
  })
}

export async function getSessions(userId) {
  return jsonFetch(`/sessions?user_id=${userId}`)
}

export async function getSessionHistory(sessionId) {
  return jsonFetch(`/sessions/${sessionId}/history`)
}

export async function deleteSession(sessionId) {
  return jsonFetch(`/sessions/${sessionId}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// WebSocket — /ws/chat?session_id=X
// ---------------------------------------------------------------------------
export function createChatWebSocket(sessionId) {
  const url = `${WS_BASE}/ws/chat?session_id=${sessionId}`
  return new WebSocket(url)
}

export function sendTextMessage(ws, sessionId, message, userId) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      session_id: sessionId,
      message,
      user_id: userId,
    }))
    return true
  }
  return false
}
