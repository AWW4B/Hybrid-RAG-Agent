// =============================================================================
// src/hooks/useVoiceChat.js
// Chat + voice state — WebSocket streaming (text) and binary audio (voice).
// Voice mode: MediaRecorder → binary WebM → backend STT→LLM→TTS → WAV back.
// Text mode:  JSON frame → backend streams tokens back.
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

const MIME = typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
  ? 'audio/webm;codecs=opus'
  : 'audio/webm'

export default function useChat({ user }) {
  const [messages, setMessages]         = useState([])
  const [isLoading, setIsLoading]       = useState(false)
  const [sessionId, setSessionId]       = useState(null)
  const [sessions, setSessions]         = useState([])
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [toolStatus, setToolStatus]     = useState(null)

  // Voice state
  const [micState, setMicState]         = useState('idle') // idle | requesting | recording | processing
  const [isPlaying, setIsPlaying]       = useState(false)
  const [voiceError, setVoiceError]     = useState(null)

  const wsRef       = useRef(null)
  const reconnTimer = useRef(null)
  const sessionRef  = useRef(null)
  const userRef     = useRef(user)
  const recorderRef = useRef(null)
  const streamRef   = useRef(null)
  const audioRef    = useRef(null)

  useEffect(() => { userRef.current = user }, [user])
  useEffect(() => { sessionRef.current = sessionId }, [sessionId])

  // ── WebSocket lifecycle ──────────────────────────────────────────
  const connect = useCallback((sid) => {
    if (!sid) return
    if (wsRef.current && wsRef.current.readyState < 2) {
      wsRef.current.close()
    }

    const ws = createChatWebSocket(sid)
    wsRef.current = ws

    ws.onopen = () => {
      clearTimeout(reconnTimer.current)
    }

    ws.onmessage = async (event) => {
      // ── Binary frame = TTS audio (WAV) ──────────────────────────
      if (event.data instanceof Blob) {
        setIsPlaying(true)
        const url = URL.createObjectURL(event.data)
        const audio = new Audio(url)
        audioRef.current = audio
        audio.onended = () => { setIsPlaying(false); URL.revokeObjectURL(url) }
        audio.onerror = () => { setIsPlaying(false); URL.revokeObjectURL(url) }
        try { await audio.play() } catch { setIsPlaying(false) }
        return
      }

      // ── Text frame = JSON control message ───────────────────────
      try {
        const msg = JSON.parse(event.data)

        // Voice turn complete
        if (msg.event === 'turn_complete') {
          if (msg.user_text || msg.assistant_text) {
            setMessages(prev => {
              const updated = [...prev]
              // Replace the voice placeholder with the actual transcript
              const placeholderIdx = updated.findLastIndex(m => m.isVoicePlaceholder)
              if (placeholderIdx !== -1) {
                updated[placeholderIdx] = {
                  ...updated[placeholderIdx],
                  content: msg.user_text || '(Unintelligible audio)',
                  isVoicePlaceholder: false,
                }
              }
              if (msg.assistant_text) {
                updated.push({
                  role: 'assistant',
                  content: msg.assistant_text,
                  timestamp: new Date().toISOString(),
                })
              }
              return updated
            })
          }
          setMicState('idle')
          setIsLoading(false)
          return
        }

        if (msg.event === 'error') {
          setVoiceError(msg.detail || 'An error occurred.')
          setMicState('idle')
          setIsLoading(false)
          return
        }

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
            setTimeout(() => setToolStatus(null), 2000)
          }
          return
        }

        // Streaming token
        if ('token' in msg && !msg.done) {
          setToolStatus(null)
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
      } catch { /* non-JSON binary, ignore */ }
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

    const init = async () => {
      setSessionsLoading(true)
      try {
        const { sessions: s } = await getSessions(user.user_id)
        setSessions(s || [])

        if (s && s.length > 0) {
          const latest = s[0]
          setSessionId(latest.session_id)
          connect(latest.session_id)
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
      recorderRef.current?.stop()
      streamRef.current?.getTracks().forEach(t => t.stop())
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

  // ── Voice: start recording ───────────────────────────────────────
  const startRecording = useCallback(async () => {
    if (micState !== 'idle') return
    setMicState('requesting')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const recorder = new MediaRecorder(stream, { mimeType: MIME })
      recorderRef.current = recorder

      // Add voice placeholder message
      setMessages(prev => [...prev, {
        role: 'user',
        content: '🎤 Voice message',
        isVoicePlaceholder: true,
        timestamp: new Date().toISOString(),
      }])
      setIsLoading(true)

      const chunks = []
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data) }
      recorder.onstop = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          const blob = new Blob(chunks, { type: MIME })
          wsRef.current.send(blob)
        }
      }

      recorder.start()
      setMicState('recording')
    } catch {
      setVoiceError('Microphone access denied.')
      setMicState('idle')
    }
  }, [micState])

  // ── Voice: stop recording ────────────────────────────────────────
  const stopRecording = useCallback(() => {
    if (micState !== 'recording') return
    recorderRef.current?.stop()
    streamRef.current?.getTracks().forEach(t => t.stop())
    setMicState('processing')
  }, [micState])

  // ── Voice: stop TTS playback ─────────────────────────────────────
  const stopSpeaking = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
      setIsPlaying(false)
    }
  }, [])

  const clearVoiceError = useCallback(() => setVoiceError(null), [])

  // ── New chat ─────────────────────────────────────────────────────
  const newChat = useCallback(async () => {
    if (!userRef.current?.user_id) return
    setIsLoading(false)
    wsRef.current?.close()
    stopSpeaking()
    setMicState('idle')

    try {
      const { session_id } = await createSession(userRef.current.user_id, 'New Chat')
      setSessionId(session_id)
      connect(session_id)
      setMessages([{
        role: 'assistant',
        content: "Hi! I'm Daraz Assistant 🛍️ — fresh chat started. What are you looking for?",
        timestamp: new Date().toISOString(),
      }])
      const { sessions: s } = await getSessions(userRef.current.user_id)
      setSessions(s || [])
    } catch (e) {
      console.error('[useChat] New chat failed:', e)
    }
  }, [connect, stopSpeaking])

  // ── Load session ─────────────────────────────────────────────────
  const loadSession = useCallback(async (sid) => {
    if (!sid) return
    setIsLoading(false)
    wsRef.current?.close()
    stopSpeaking()
    setMicState('idle')
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
  }, [connect, stopSpeaking])

  // ── Delete session ───────────────────────────────────────────────
  const removeSession = useCallback(async (sid) => {
    try {
      await deleteSession(sid)
      setSessions(prev => prev.filter(s => s.session_id !== sid))
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
    // Voice
    micState,
    isPlaying,
    voiceError,
    // Actions
    send,
    newChat,
    loadSession,
    removeSession,
    refreshSessions,
    startRecording,
    stopRecording,
    stopSpeaking,
    clearVoiceError,
  }
}
