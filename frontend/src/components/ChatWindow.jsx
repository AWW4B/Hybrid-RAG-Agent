// =============================================================================
// src/components/ChatWindow.jsx
// Core chat shell — messages list + input bar + tool indicator
// =============================================================================
import { useEffect, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import MessageBubble from './MessageBubble.jsx'
import TypingIndicator from './TypingIndicator.jsx'
import QuickActions from './QuickActions.jsx'
import InputBar from './InputBar.jsx'
import ToolIndicator from './ToolIndicator.jsx'

export default function ChatWindow({ chat, backendStatus }) {
  const { messages, isLoading, toolStatus, send } = chat
  const bottomRef = useRef(null)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading, toolStatus])

  const showQuickActions = messages.length === 1 && messages[0].role === 'assistant'

  return (
    <div className="flex flex-col h-full relative">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 custom-scrollbar">
        <div className="max-w-2xl mx-auto w-full flex flex-col gap-1">
          <AnimatePresence initial={false}>
            {messages.map((msg, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
              >
                <MessageBubble message={msg} isLast={i === messages.length - 1} />
              </motion.div>
            ))}
          </AnimatePresence>

          {showQuickActions && (
            <div className="mt-4">
              <QuickActions onSelect={send} />
            </div>
          )}

          {/* Typing indicator */}
          <AnimatePresence>
            {isLoading && !messages.some(m => m.streaming) && !toolStatus && <TypingIndicator />}
          </AnimatePresence>

          <div ref={bottomRef} className="h-24" />
        </div>
      </div>

      {/* Input bar + tool indicator — fixed at bottom */}
      <div className="flex-shrink-0 px-4 pb-4">
        <div className="max-w-2xl mx-auto">
          <InputBar onSend={send} disabled={false} />
          <ToolIndicator toolStatus={toolStatus} />
        </div>
      </div>
    </div>
  )
}
