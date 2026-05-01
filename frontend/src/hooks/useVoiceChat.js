// =============================================================================
// src/hooks/useChat.js
// Chat state hook — WebSocket text streaming + session management.
// Matched to new backend: /ws/chat, {session_id, message, user_id}
// =============================================================================
import { useState, useRef, useCallback, useEffect } from 'react'
import {
  createChatWebSocket,
  sendTextMessage,
  createSession,
  getSessions,
  getSessionHistory,
  deleteSession,
} from '../utils/api.js'

export default function useChat({ user }) {
  const [messages, setMessages]     = useState([])
  const [isLoading, setIsLoading]   = useState(false)
  const [sessionId, setSessionId]   = useState(null)
  const [sessions, setSessions]     = useState([])
  const [sessionsLoading, setSessionsLoading] = useState(false)

  const wsRef       = useRef(null)
  const reconnTimer = useRef(null)
  const sessionRef  = useRef(null)
  const userRef     = useRef(user)

  useEffect(() => { userRef.current = user }, [user])
  useEffect(() => { sessionRef.current = sessionId }, [sessionId])

  const [toolStatus, setToolStatus] = useState(null) // {status: 'running'|'done', name?, tools_used?}

  // ── WebSocket lifecycle ──────────────────────────────────────────
  const connect = useCallback((sid) => {
    if (!sid) return
    // Close existing
    if (wsRef.current && wsRef.current.readyState < 2) {
      wsRef.current.close()
    }

    const ws = createChatWebSocket(sid)
    wsRef.current = ws

    ws.onopen = () => {
      clearTimeout(reconnTimer.current)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        if (msg.error) {
          console.error('[ws] Server error:', msg.error)
          setIsLoading(false)
          setToolStatus(null)
          return
        }

        // Tool status indicator
        if ('tool_status' in msg) {
          if (msg.tool_status === 'running') {
            setToolStatus({ status: 'running', name: msg.tool_name || 'Processing...' })
          } else if (msg.tool_status === 'done') {
            setToolStatus({ status: 'done', tools_used: msg.tools_used || [] })
            // Clear after a short delay so user sees the result
            setTimeout(() => setToolStatus(null), 2000)
          }
          return
        }

        // Streaming token
        if ('token' in msg && !msg.done) {
          setToolStatus(null) // Clear tool status when tokens start
          setMessages(prev => {
            const last = prev[prev.length - 1]
            if (last && last.streaming) {
              return [...prev.slice(0, -1), { ...last, content: last.content + msg.token }]
            }
            return [...prev, {
              role: 'assistant',
              content: msg.token,
              streaming: true,
              timestamp: new Date().toISOString(),
            }]
          })
          return
        }

        // Done frame
        if (msg.done) {
          setMessages(prev => {
            const last = prev[prev.length - 1]
            if (last && last.streaming) {
              return [...prev.slice(0, -1), {
                ...last,
                content: msg.full_response || last.content,
                streaming: false,
                latency_ms: msg.latency_ms ?? null,
              }]
            }
            return prev
          })
          setIsLoading(false)
          return
        }
      } catch { /* non-JSON, ignore */ }
    }

    ws.onclose = () => {
      reconnTimer.current = setTimeout(() => {
        if (sessionRef.current) connect(sessionRef.current)
      }, 2000)
    }

    ws.onerror = () => {
      setIsLoading(false)
      setToolStatus(null)
    }
  }, [])

  // ── Initialize on mount ──────────────────────────────────────────
  useEffect(() => {
    if (!user?.user_id) return

    // Load sessions and auto-create one if none exist
    const init = async () => {
      setSessionsLoading(true)
      try {
        const { sessions: s } = await getSessions(user.user_id)
        setSessions(s || [])

        if (s && s.length > 0) {
          // Load most recent session
          const latest = s[0]
          setSessionId(latest.session_id)
          connect(latest.session_id)
          // Load history
          try {
            const { messages: hist } = await getSessionHistory(latest.session_id)
            if (hist && hist.length > 0) {
              setMessages(hist.map(m => ({
                role: m.role,
                content: m.content,
                timestamp: new Date().toISOString(),
              })))
            } else {
              setMessages([{
                role: 'assistant',
                content: "Hi! I'm Daraz Assistant 🛍️ — your AI shopping guide. What can I help you find today?",
                timestamp: new Date().toISOString(),
              }])
            }
          } catch {
            setMessages([{
              role: 'assistant',
              content: "Hi! I'm Daraz Assistant 🛍️ — your AI shopping guide. What can I help you find today?",
              timestamp: new Date().toISOString(),
            }])
          }
        } else {
          // Create first session
          const { session_id } = await createSession(user.user_id, 'New Chat')
          setSessionId(session_id)
          setSessions([{ session_id, title: 'New Chat', created_at: new Date().toISOString(), updated_at: new Date().toISOString() }])
          connect(session_id)
          setMessages([{
            role: 'assistant',
            content: "Hi! I'm Daraz Assistant 🛍️ — your AI shopping guide. What can I help you find today?",
            timestamp: new Date().toISOString(),
          }])
        }
      } catch (e) {
        console.error('[useChat] Init failed:', e)
        // Create a session anyway
        try {
          const { session_id } = await createSession(user.user_id, 'New Chat')
          setSessionId(session_id)
          connect(session_id)
          setMessages([{
            role: 'assistant',
            content: "Hi! I'm Daraz Assistant 🛍️ — your AI shopping guide. What can I help you find today?",
            timestamp: new Date().toISOString(),
          }])
        } catch {}
      } finally {
        setSessionsLoading(false)
      }
    }

    init()

    return () => {
      clearTimeout(reconnTimer.current)
      wsRef.current?.close()
    }
  }, [user?.user_id, connect])

  // ── Send text ────────────────────────────────────────────────────
  const send = useCallback((text) => {
    if (!text.trim() || !sessionRef.current || !userRef.current) return
    setMessages(prev => [...prev, {
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }])
    setIsLoading(true)
    sendTextMessage(wsRef.current, sessionRef.current, text, userRef.current.user_id)
  }, [])

  // ── New chat ─────────────────────────────────────────────────────
  const newChat = useCallback(async () => {
    if (!userRef.current?.user_id) return
    setIsLoading(false)
    wsRef.current?.close()

    try {
      const { session_id } = await createSession(userRef.current.user_id, 'New Chat')
      setSessionId(session_id)
      connect(session_id)
      setMessages([{
        role: 'assistant',
        content: "Hi! I'm Daraz Assistant 🛍️ — fresh chat started. What are you looking for?",
        timestamp: new Date().toISOString(),
      }])
      // Refresh sessions list
      const { sessions: s } = await getSessions(userRef.current.user_id)
      setSessions(s || [])
    } catch (e) {
      console.error('[useChat] New chat failed:', e)
    }
  }, [connect])

  // ── Load session ─────────────────────────────────────────────────
  const loadSession = useCallback(async (sid) => {
    if (!sid) return
    setIsLoading(false)
    wsRef.current?.close()
    setSessionId(sid)
    connect(sid)

    try {
      const { messages: hist } = await getSessionHistory(sid)
      if (hist && hist.length > 0) {
        setMessages(hist.map(m => ({
          role: m.role,
          content: m.content,
          timestamp: new Date().toISOString(),
        })))
      } else {
        setMessages([{
          role: 'assistant',
          content: "This chat is empty. Ask me anything!",
          timestamp: new Date().toISOString(),
        }])
      }
    } catch {
      setMessages([{
        role: 'assistant',
        content: "Couldn't load chat history. Start fresh!",
        timestamp: new Date().toISOString(),
      }])
    }
  }, [connect])

  // ── Delete session ───────────────────────────────────────────────
  const removeSession = useCallback(async (sid) => {
    try {
      await deleteSession(sid)
      setSessions(prev => prev.filter(s => s.session_id !== sid))
      // If we deleted the current session, start a new one
      if (sid === sessionRef.current) {
        await newChat()
      }
    } catch (e) {
      console.error('[useChat] Delete failed:', e)
    }
  }, [newChat])

  // ── Refresh sessions ─────────────────────────────────────────────
  const refreshSessions = useCallback(async () => {
    if (!userRef.current?.user_id) return
    try {
      const { sessions: s } = await getSessions(userRef.current.user_id)
      setSessions(s || [])
    } catch {}
  }, [])

  return {
    messages,
    isLoading,
    toolStatus,
    sessionId,
    sessions,
    sessionsLoading,
    send,
    newChat,
    loadSession,
    removeSession,
    refreshSessions,
  }
}
