import React, { useState } from 'react'

export interface Soundbite {
  id: string
  title: string
  speaker: string
  startSec: number
  endSec: number
  category: 'decision' | 'milestone' | 'key_insight' | 'feedback'
  quote: string
  likes: number
}

interface MeetingHighlightReelsProps {
  meeting: any
  theme: 'light' | 'dark'
  onSeekPlayback?: (sec: number) => void
}

export const MeetingHighlightReels: React.FC<MeetingHighlightReelsProps> = ({
  meeting,
  theme,
  onSeekPlayback,
}) => {
  const isDark = theme === 'dark'
  const [activeClipId, setActiveClipId] = useState<string | null>(null)
  const [copiedShareNotice, setCopiedShareNotice] = useState<string | null>(null)
  const [likedClips, setLikedClips] = useState<Record<string, number>>({})

  const defaultClips: Soundbite[] = [
    {
      id: 'clip-1',
      title: 'Final Architecture Consensus',
      speaker: 'Sarah Kim',
      startSec: 7,
      endSec: 22,
      category: 'decision',
      quote: 'I will finalize the technical architecture specification by Friday.',
      likes: 4,
    },
    {
      id: 'clip-2',
      title: 'Backend API Review Commitment',
      speaker: 'Marcus Lee',
      startSec: 18,
      endSec: 36,
      category: 'milestone',
      quote: 'Let us review the API changes with the backend team tomorrow.',
      likes: 2,
    },
    {
      id: 'clip-3',
      title: 'Performance & Latency Target',
      speaker: 'Jordan Davis',
      startSec: 42,
      endSec: 58,
      category: 'key_insight',
      quote: 'Our goal is sub-100ms response time across all vector search queries.',
      likes: 6,
    },
  ]

  const clips = defaultClips

  const handlePlayClip = (clip: Soundbite) => {
    setActiveClipId(clip.id)
    if (onSeekPlayback) {
      onSeekPlayback(clip.startSec)
    }
  }

  const handleShareClip = (clip: Soundbite) => {
    const shareUrl = `${window.location.origin}/#meeting/${meeting?.id || 1}?t=${clip.startSec}`
    navigator.clipboard.writeText(`🎧 Listen to this key moment from "${meeting?.title || 'Meeting'}": "${clip.quote}" - ${shareUrl}`)
    setCopiedShareNotice(clip.id)
    setTimeout(() => setCopiedShareNotice(null), 3000)
  }

  const handleToggleLike = (clipId: string, currentLikes: number) => {
    setLikedClips((prev) => ({
      ...prev,
      [clipId]: (prev[clipId] ?? currentLikes) + 1,
    }))
  }

  const bgCard = isDark ? '#1a162b' : '#ffffff'
  const borderCard = isDark ? '#2b2349' : '#e8e5ec'
  const textColor = isDark ? '#f4f2fa' : '#1e1b33'
  const subTextColor = isDark ? '#9e99ad' : '#6b7280'

  const getCategoryBadge = (cat: Soundbite['category']) => {
    switch (cat) {
      case 'decision':
        return { label: 'Decision', bg: '#dcfce7', color: '#166534', icon: '🎯' }
      case 'milestone':
        return { label: 'Milestone', bg: '#ede9fe', color: '#6d28d9', icon: '🚀' }
      case 'key_insight':
        return { label: 'Key Insight', bg: '#e0f2fe', color: '#0369a1', icon: '💡' }
      default:
        return { label: 'Highlight', bg: '#fef3c7', color: '#b45309', icon: '✨' }
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      {/* Header Banner */}
      <div
        style={{
          background: isDark ? 'linear-gradient(135deg, #241b47, #191433)' : 'linear-gradient(135deg, #f5f3ff, #ede9fe)',
          border: `1px solid ${isDark ? '#3d2e6e' : '#c4b5fd'}`,
          borderRadius: '14px',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '12px',
              background: '#7c3aed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '20px',
              color: '#fff',
            }}
          >
            🎬
          </div>
          <div>
            <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: textColor }}>
              AI Video Soundbites & Highlight Reels
            </h4>
            <p style={{ margin: '2px 0 0', fontSize: '12px', color: subTextColor }}>
              AI automatically extracted the 3 most pivotal moments into 15–30 second playable clips
            </p>
          </div>
        </div>

        <span
          style={{
            fontSize: '11px',
            fontWeight: 700,
            background: isDark ? '#32235c' : '#ffffff',
            color: '#7c3aed',
            padding: '4px 10px',
            borderRadius: '20px',
            border: '1px solid #7c3aed',
          }}
        >
          {clips.length} Clips Available
        </span>
      </div>

      {/* Soundbites Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
        {clips.map((clip) => {
          const isPlaying = activeClipId === clip.id
          const badge = getCategoryBadge(clip.category)
          const durationSec = clip.endSec - clip.startSec
          const likesCount = likedClips[clip.id] ?? clip.likes

          return (
            <div
              key={clip.id}
              style={{
                background: bgCard,
                border: isPlaying ? '2px solid #7c3aed' : `1px solid ${borderCard}`,
                borderRadius: '14px',
                padding: '18px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                boxShadow: isPlaying ? '0 8px 24px rgba(124, 58, 237, 0.25)' : '0 4px 16px rgba(0,0,0,0.03)',
                transition: 'all 0.2s ease',
              }}
            >
              {/* Card Top: Category Badge & Duration */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '3px 8px',
                    borderRadius: '6px',
                    background: badge.bg,
                    color: badge.color,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <span>{badge.icon}</span>
                  <span>{badge.label}</span>
                </span>

                <span style={{ fontSize: '11px', fontFamily: 'monospace', color: subTextColor, background: isDark ? '#231e3d' : '#f4f2fa', padding: '2px 6px', borderRadius: '4px' }}>
                  ⏱ {clip.startSec}s – {clip.endSec}s ({durationSec}s)
                </span>
              </div>

              {/* Title & Quote */}
              <div>
                <h5 style={{ margin: '0 0 6px', fontSize: '14px', fontWeight: 700, color: textColor }}>
                  {clip.title}
                </h5>
                <blockquote
                  style={{
                    margin: 0,
                    padding: '8px 12px',
                    background: isDark ? '#231e3d' : '#f9f8fc',
                    borderLeft: '3px solid #7c3aed',
                    borderRadius: '0 8px 8px 0',
                    fontSize: '12px',
                    color: textColor,
                    fontStyle: 'italic',
                    lineHeight: 1.45,
                  }}
                >
                  "{clip.quote}"
                </blockquote>
              </div>

              {/* Speaker & Simulated Audio Waveform */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '4px' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: '#6d55d8' }}>
                  🗣️ {clip.speaker}
                </span>

                {/* Animated Waveform Bars */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '3px', height: '18px' }}>
                  {[12, 18, 8, 22, 14, 20, 10, 16].map((h, i) => (
                    <span
                      key={i}
                      style={{
                        width: '3px',
                        height: isPlaying ? `${h}px` : `${Math.max(4, h / 2)}px`,
                        background: isPlaying ? '#7c3aed' : subTextColor,
                        borderRadius: '2px',
                        transition: 'height 0.2s ease',
                      }}
                    />
                  ))}
                </div>
              </div>

              {/* Card Footer Actions */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '8px', borderTop: `1px solid ${borderCard}` }}>
                <button
                  type="button"
                  onClick={() => handlePlayClip(clip)}
                  style={{
                    background: isPlaying ? '#22c55e' : '#7c3aed',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '6px 14px',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    boxShadow: isPlaying ? '0 2px 10px rgba(34, 197, 94, 0.4)' : '0 2px 10px rgba(124, 58, 237, 0.3)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <span>{isPlaying ? '▶ Playing' : '▶ Play Clip'}</span>
                </button>

                <div style={{ display: 'flex', gap: '6px' }}>
                  {/* Like Button */}
                  <button
                    type="button"
                    onClick={() => handleToggleLike(clip.id, clip.likes)}
                    title="Bookmark this key moment"
                    style={{
                      background: 'transparent',
                      border: `1px solid ${borderCard}`,
                      borderRadius: '6px',
                      padding: '5px 8px',
                      fontSize: '11px',
                      color: textColor,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <span>❤️</span>
                    <span>{likesCount}</span>
                  </button>

                  {/* Share Clip Button */}
                  <button
                    type="button"
                    onClick={() => handleShareClip(clip)}
                    title="Copy direct link to this soundbite"
                    style={{
                      background: copiedShareNotice === clip.id ? '#22c55e' : 'transparent',
                      border: `1px solid ${copiedShareNotice === clip.id ? '#22c55e' : borderCard}`,
                      borderRadius: '6px',
                      padding: '5px 10px',
                      fontSize: '11px',
                      fontWeight: 600,
                      color: copiedShareNotice === clip.id ? '#fff' : textColor,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {copiedShareNotice === clip.id ? '✓ Copied!' : '🔗 Share'}
                  </button>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
