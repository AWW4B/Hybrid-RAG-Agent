// =============================================================================
// src/components/FullPageChat.jsx
// Full-screen chat layout
// =============================================================================
import useVoiceChat from '../hooks/useVoiceChat.js'
import ChatWindow from './ChatWindow.jsx'

export default function FullPageChat({ backendStatus }) {
  const chat = useVoiceChat()
  return (
    <div className="h-screen w-full flex flex-col bg-[#f5f5f5]">
      <div className="flex-1 max-w-3xl w-full mx-auto p-4 flex flex-col min-h-0">
        <ChatWindow chat={chat} backendStatus={backendStatus} />
      </div>
    </div>
  )
}
