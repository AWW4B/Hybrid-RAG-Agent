// =============================================================================
// src/components/AudioWaveform.jsx
// Animated equalizer bars — used in VoiceMicButton and ChatHeader
// =============================================================================
export default function AudioWaveform({ bars = 5, className = '', color = 'currentColor' }) {
  return (
    <div className={`flex items-end gap-[2px] ${className}`} style={{ color }}>
      {Array.from({ length: bars }).map((_, i) => (
        <span key={i} className="eq-bar" style={{ height: '4px' }} />
      ))}
    </div>
  )
}
