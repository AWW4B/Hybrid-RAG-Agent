// =============================================================================
// src/components/FullPageChat.jsx
// Full-screen chat layout
// =============================================================================
import useVoiceChat from '../hooks/useVoiceChat.js'
import ChatWindow from './ChatWindow.jsx'
import SessionSidebar from './SessionSidebar.jsx'

export default function FullPageChat({ backendStatus, token, user }) {
  const chat = useVoiceChat({ token })
  
  return (
    <div className="h-screen w-full flex bg-[#1a0f00] relative">
      {/* Persisted Sidebar in Full Page Mode */}
      <div className="hidden lg:block w-[260px] border-r border-white/5 bg-[#2a1a08]">
        <SessionSidebar
          currentSessionId={chat.sessionId}
          onLoadSession={chat.loadSession}
          onNewChat={chat.reset}
          isOpen={true}
          isStatic={true}
        />
      </div>

      {/* Main Chat Canvas */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        <div className="flex-1 max-w-[720px] w-full mx-auto flex flex-col min-h-0">
          <ChatWindow chat={chat} backendStatus={backendStatus} isImmersive={true} user={user} />
        </div>
      </div>
    </div>
  )
}
