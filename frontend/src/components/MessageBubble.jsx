// =============================================================================
// src/components/MessageBubble.jsx
// Single message row — user (right, orange) or bot (left, white)
// Supports streaming cursor, voice messages, error/cancelled states
// =============================================================================
import { Volume2 } from 'lucide-react'
import AudioWaveform from './AudioWaveform.jsx'

function formatTime(iso) {
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
  catch { return '' }
}

export default function MessageBubble({ message, isPlaying, onStopSpeaking }) {
  const { role, content, timestamp, streaming, isError, cancelled, latency_ms, isVoice } = message
  const isUser = role === 'user'

  return (
    <div className={`flex items-end gap-2 px-4 py-1 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center
                    font-bold text-xs text-white shadow
                    ${isUser ? 'bg-gray-700' : ''}`}
        style={!isUser ? { background: 'linear-gradient(135deg, #F57224, #ff8c42)' } : {}}
      >
        {isUser ? 'U' : 'D'}
      </div>

      {/* Bubble */}
      <div className={`max-w-[75%] flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap shadow-sm
                      ${isUser
                        ? 'bg-[#F57224] text-white rounded-tr-sm'
                        : isError
                          ? 'bg-red-50 text-gray-800 rounded-tl-sm border border-red-200'
                          : isPlaying
                            ? 'bg-white text-gray-800 rounded-tl-sm border border-gray-100 ring-2 ring-[#F57224]/30'
                            : 'bg-white text-gray-800 rounded-tl-sm border border-gray-100'
                      }`}
        >
          {/* Voice message: show waveform + label */}
          {isVoice ? (
            <div className="flex items-center gap-2 text-white/90">
              <AudioWaveform bars={5} color="currentColor" />
              <span className="text-xs italic">Voice message</span>
            </div>
          ) : (
            content
          )}

          {/* Streaming cursor */}
          {streaming && (
            <span className="stream-cursor inline-block w-1.5 h-4 bg-[#F57224] ml-0.5 align-middle rounded-sm" />
          )}

          {/* Cancelled note */}
          {cancelled && (
            <span className="block text-[10px] italic text-[#F57224] mt-1">Generation stopped</span>
          )}
        </div>

        {/* Footer: timestamp + latency + speak button */}
        <div className={`flex items-center gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
          <span className="text-[10px] text-gray-400">
            {formatTime(timestamp)}
            {latency_ms && <span> • {(latency_ms / 1000).toFixed(1)}s</span>}
          </span>

          {/* Speak/stop button on bot messages */}
          {!isUser && !streaming && !isError && (
            isPlaying
              ? (
                <button
                  onClick={onStopSpeaking}
                  className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px]
                             border border-[#F57224] text-[#F57224]"
                >
                  <AudioWaveform bars={3} color="#F57224" />
                  <span>Stop</span>
                </button>
              )
              : (
                <div className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border border-gray-200 text-gray-400">
                  <Volume2 size={10} />
                  <span>Playing via voice</span>
                </div>
              )
          )}
        </div>
      </div>
    </div>
  )
}
