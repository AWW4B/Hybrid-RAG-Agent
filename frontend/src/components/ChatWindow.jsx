// =============================================================================
// src/components/ChatWindow.jsx
// Core chat shell — wires the useVoiceChat hook to all sub-components
// =============================================================================
import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import ChatHeader from './ChatHeader.jsx'
import MessageBubble from './MessageBubble.jsx'
import TypingIndicator from './TypingIndicator.jsx'
import QuickActions from './QuickActions.jsx'
import InputBar from './InputBar.jsx'
import SessionSidebar from './SessionSidebar.jsx'

export default function ChatWindow({ chat, onMinimize, onClose, backendStatus }) {
  const {
    messages, isLoading, micState, isPlaying, status,
    turnsUsed, turnsMax, voiceError,
    send, startRecording, stopRecording, stopSpeaking,
    reset, loadSession, clearVoiceError, sessionId,
  } = chat

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const bottomRef = useRef(null)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Auto-dismiss voice error after 4s
  useEffect(() => {
    if (!voiceError) return
    const t = setTimeout(clearVoiceError, 4000)
    return () => clearTimeout(t)
  }, [voiceError, clearVoiceError])

  const showQuickActions = messages.length === 1 && messages[0].role === 'assistant'

  return (
    <div className="flex flex-col h-full bg-[#f5f5f5] rounded-2xl shadow-2xl overflow-hidden">
      <SessionSidebar
        currentSessionId={sessionId}
        onLoadSession={loadSession}
        onNewChat={reset}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <ChatHeader
        onReset={reset}
        onMinimize={onMinimize}
        onClose={onClose}
        onToggleHistory={() => setSidebarOpen(v => !v)}
        turnsUsed={turnsUsed}
        turnsMax={turnsMax}
        status={status}
        isPlaying={isPlaying}
        backendStatus={backendStatus}
      />

      {/* Voice error toast */}
      <AnimatePresence>
        {voiceError && (
          <motion.div
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            className="mx-3 mt-2 px-3 py-2 bg-red-50 border border-red-200 rounded-xl text-xs text-red-600 flex justify-between items-center"
          >
            <span>⚠️ {voiceError}</span>
            <button onClick={clearVoiceError} className="ml-2 text-red-400 hover:text-red-600">✕</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Session ended banner */}
      {status === 'ended' && (
        <div className="mx-3 mt-2 px-3 py-2 bg-orange-50 border border-orange-200 rounded-xl text-xs text-orange-700 flex justify-between items-center">
          <span>Session limit reached.</span>
          <button onClick={reset} className="font-medium underline hover:text-orange-900">Start New Chat</button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 chat-scroll py-3 min-h-0">
        <AnimatePresence initial={false}>
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              <MessageBubble
                message={msg}
                isLast={i === messages.length - 1}
                isPlaying={isPlaying && i === messages.length - 1 && msg.role === 'assistant'}
                onStopSpeaking={stopSpeaking}
              />
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Quick actions — only on fresh welcome */}
        {showQuickActions && <QuickActions onSelect={send} />}

        {/* Typing indicator */}
        <AnimatePresence>
          {isLoading && !messages.some(m => m.streaming) && <TypingIndicator />}
        </AnimatePresence>

        <div ref={bottomRef} />
      </div>

      <InputBar
        onSend={send}
        disabled={status === 'ended'}
        micState={micState}
        onStartRecording={startRecording}
        onStopRecording={stopRecording}
      />
    </div>
  )
}
