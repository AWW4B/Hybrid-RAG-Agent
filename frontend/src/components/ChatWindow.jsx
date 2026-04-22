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

export default function ChatWindow({ chat, onMinimize, onClose, backendStatus, isImmersive, user }) {
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
    <div className={`flex-1 flex flex-col min-h-0 ${isImmersive ? 'bg-transparent' : 'bg-[#1a0f00] rounded-[2rem] shadow-2xl shadow-black/40 overflow-hidden border border-white/5'}`}>
      {!isImmersive && (
        <SessionSidebar
          currentSessionId={sessionId}
          onLoadSession={loadSession}
          onNewChat={reset}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
      )}

      <ChatHeader
        onReset={reset}
        onMinimize={onMinimize}
        onClose={onClose}
        onToggleHistory={isImmersive ? null : () => setSidebarOpen(v => !v)}
        turnsUsed={turnsUsed}
        turnsMax={turnsMax}
        status={status}
        isPlaying={isPlaying}
        backendStatus={backendStatus}
        user={user}
      />

      {/* Messages Area */}
      <div className="flex-1 relative overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto px-4 py-8 custom-scrollbar scroll-smooth">
          <div className="max-w-[720px] mx-auto w-full flex flex-col gap-2">
            <AnimatePresence initial={false}>
              {messages.map((msg, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: msg.role === 'user' ? 20 : -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ type: 'spring', damping: 25, stiffness: 200 }}
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

            {showQuickActions && (
              <div className="mt-8">
                <QuickActions onSelect={send} />
              </div>
            )}

            {/* Typing indicator */}
            <AnimatePresence>
              {isLoading && !messages.some(m => m.streaming) && <TypingIndicator />}
            </AnimatePresence>

            <div ref={bottomRef} className="h-32" />
          </div>
        </div>

        {/* Floating Input Bar Overlay */}
        <InputBar
          onSend={send}
          disabled={status === 'ended'}
          micState={micState}
          onStartRecording={startRecording}
          onStopRecording={stopRecording}
        />
      </div>

      {/* Alerts Overlay (Toasts) */}
      <div className="absolute top-20 left-1/2 -translate-x-1/2 w-full max-w-md px-6 pointer-events-none z-50">
        <AnimatePresence>
          {voiceError && (
            <motion.div
              initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.9 }}
              className="pointer-events-auto p-3 bg-[#3d2a14] border border-red-900/30 rounded-xl glass-shadow text-xs text-red-400 flex justify-between items-center gap-2"
            >
              <span>⚠️ {voiceError}</span>
              <button onClick={clearVoiceError} className="hover:text-red-300">✕</button>
            </motion.div>
          )}
          {status === 'ended' && (
            <motion.div
               initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}
               className="pointer-events-auto mt-2 p-3 bg-orange-950/40 border border-[#F57224]/30 rounded-xl glass-shadow text-xs text-[#c4a882] flex justify-between items-center"
            >
              <span>Ledger limit reached.</span>
              <button onClick={reset} className="font-bold text-[#F57224] underline ml-4 tracking-widest uppercase">Start New</button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
