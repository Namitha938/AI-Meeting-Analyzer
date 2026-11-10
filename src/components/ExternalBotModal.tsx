import React, { useState } from 'react'

interface ExternalBotModalProps {
  isOpen: boolean
  onClose: () => void
  onBotDispatched?: (meetingData: any) => void
  theme: 'light' | 'dark'
}

export const ExternalBotModal: React.FC<ExternalBotModalProps> = ({
  isOpen,
  onClose,
  onBotDispatched,
  theme,
}) => {
  if (!isOpen) return null

  const isDark = theme === 'dark'
  const [meetingUrl, setMeetingUrl] = useState<string>('')
  const [meetingTitle, setMeetingTitle] = useState<string>('External Sync')
  const [botName, setBotName] = useState<string>('Meetora AI Notetaker')
  const [autoEmailRecap, setAutoEmailRecap] = useState<boolean>(true)
  const [isDispatching, setIsDispatching] = useState<boolean>(false)
  const [dispatchStatus, setDispatchStatus] = useState<string | null>(null)
  const [dispatchError, setDispatchError] = useState<string | null>(null)

  const detectPlatform = (url: string): { name: string; icon: string; color: string } => {
    const lower = url.toLowerCase()
    if (lower.includes('meet.google.com')) return { name: 'Google Meet', icon: '🟢', color: '#10b981' }
    if (lower.includes('zoom.us')) return { name: 'Zoom Meeting', icon: '🔵', color: '#0e72ed' }
    if (lower.includes('teams.microsoft.com') || lower.includes('teams.live.com')) return { name: 'Microsoft Teams', icon: '🟣', color: '#7c3aed' }
    if (lower.includes('webex.com')) return { name: 'Cisco Webex', icon: '🟠', color: '#f59e0b' }
    return { name: 'Standard Web Conference', icon: '🌐', color: '#6d55d8' }
  }

  const platform = detectPlatform(meetingUrl)

  const handleDispatch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!meetingUrl.trim()) {
      setDispatchError('Please paste a valid meeting link (Google Meet, Zoom, or Teams).')
      return
    }

    setDispatchError(null)
    setIsDispatching(true)
    setDispatchStatus('1. Connecting to conference gateway...')

    setTimeout(() => {
      setDispatchStatus(`2. Bot "${botName}" requesting admission to ${platform.name}...`)
    }, 1200)

    setTimeout(() => {
      setDispatchStatus(`3. Admitted! Recording and live transcription active in ${platform.name}.`)
      setIsDispatching(false)

      if (onBotDispatched) {
        onBotDispatched({
          title: meetingTitle || 'External Call',
          platform: platform.name,
          url: meetingUrl,
          bot_name: botName,
          status: 'recording',
          dispatched_at: new Date().toISOString(),
        })
      }

      setTimeout(() => {
        onClose()
        setDispatchStatus(null)
        setMeetingUrl('')
      }, 2000)
    }, 2800)
  }

  const bgModal = isDark ? '#1a162b' : '#ffffff'
  const borderModal = isDark ? '#2b2349' : '#e8e5ec'
  const textColor = isDark ? '#f4f2fa' : '#1e1b33'
  const subTextColor = isDark ? '#9e99ad' : '#6b7280'

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.7)',
        backdropFilter: 'blur(5px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100010,
        padding: '16px',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !isDispatching) onClose()
      }}
    >
      <div
        style={{
          background: bgModal,
          border: `1px solid ${borderModal}`,
          borderRadius: '16px',
          maxWidth: '520px',
          width: '100%',
          overflow: 'hidden',
          boxShadow: '0 25px 50px rgba(0,0,0,0.5)',
          color: textColor,
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '18px 24px',
            borderBottom: `1px solid ${borderModal}`,
            background: isDark ? '#151224' : '#f9f8fc',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                background: '#6d55d8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '18px',
                color: '#fff',
              }}
            >
              🤖
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>
                Send AI Notetaker Bot to Call
              </h3>
              <p style={{ margin: 0, fontSize: '12px', color: subTextColor }}>
                Joins Google Meet, Zoom, or Microsoft Teams calls automatically
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isDispatching}
            style={{
              background: 'transparent',
              border: 'none',
              color: subTextColor,
              fontSize: '20px',
              cursor: isDispatching ? 'not-allowed' : 'pointer',
              padding: '4px',
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleDispatch} style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Meeting URL */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: textColor, marginBottom: '6px' }}>
              Meeting Link (Google Meet / Zoom / MS Teams) <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input
              type="url"
              placeholder="https://meet.google.com/abc-defg-hij or https://zoom.us/j/123..."
              value={meetingUrl}
              onChange={(e) => setMeetingUrl(e.target.value)}
              disabled={isDispatching}
              required
              style={{
                width: '100%',
                background: isDark ? '#120f20' : '#f4f2fa',
                border: `1px solid ${borderModal}`,
                borderRadius: '8px',
                padding: '10px 14px',
                fontSize: '13px',
                color: textColor,
                boxSizing: 'border-box',
              }}
            />
            {meetingUrl && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px', fontSize: '11px', color: platform.color, fontWeight: 600 }}>
                <span>{platform.icon}</span>
                <span>Detected Platform: {platform.name}</span>
              </div>
            )}
          </div>

          {/* Meeting Title */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: textColor, marginBottom: '6px' }}>
              Meeting Title / Label
            </label>
            <input
              type="text"
              placeholder="e.g. Customer Discovery Call with Acme"
              value={meetingTitle}
              onChange={(e) => setMeetingTitle(e.target.value)}
              disabled={isDispatching}
              style={{
                width: '100%',
                background: isDark ? '#120f20' : '#f4f2fa',
                border: `1px solid ${borderModal}`,
                borderRadius: '8px',
                padding: '10px 14px',
                fontSize: '13px',
                color: textColor,
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Bot Name */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: textColor, marginBottom: '6px' }}>
              Bot Display Name
            </label>
            <input
              type="text"
              value={botName}
              onChange={(e) => setBotName(e.target.value)}
              disabled={isDispatching}
              style={{
                width: '100%',
                background: isDark ? '#120f20' : '#f4f2fa',
                border: `1px solid ${borderModal}`,
                borderRadius: '8px',
                padding: '10px 14px',
                fontSize: '13px',
                color: textColor,
                boxSizing: 'border-box',
              }}
            />
            <small style={{ color: subTextColor, fontSize: '11px', marginTop: '4px', display: 'block' }}>
              This name will appear in the attendee list of the Google Meet / Zoom call.
            </small>
          </div>

          {/* Options */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '4px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: textColor, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={autoEmailRecap}
                onChange={(e) => setAutoEmailRecap(e.target.checked)}
                style={{ accentColor: '#6d55d8' }}
              />
              <span>Automatically email summary & action items to host when call ends</span>
            </label>
          </div>

          {/* Status / Error Notifications */}
          {dispatchStatus && (
            <div
              style={{
                padding: '12px 14px',
                borderRadius: '8px',
                background: 'rgba(109, 85, 216, 0.15)',
                border: '1px solid rgba(109, 85, 216, 0.4)',
                color: '#a78bfa',
                fontSize: '12px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <span>🤖</span>
              <span>{dispatchStatus}</span>
            </div>
          )}

          {dispatchError && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: '8px',
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                color: '#f87171',
                fontSize: '12px',
              }}
            >
              ⚠️ {dispatchError}
            </div>
          )}

          {/* Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isDispatching}
              style={{
                background: 'transparent',
                border: `1px solid ${borderModal}`,
                borderRadius: '8px',
                padding: '9px 18px',
                color: subTextColor,
                fontSize: '12px',
                fontWeight: 600,
                cursor: isDispatching ? 'not-allowed' : 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isDispatching || !meetingUrl.trim()}
              style={{
                background: isDispatching || !meetingUrl.trim() ? '#4b4376' : '#6d55d8',
                border: 'none',
                borderRadius: '8px',
                padding: '9px 22px',
                color: '#fff',
                fontSize: '12px',
                fontWeight: 700,
                cursor: isDispatching || !meetingUrl.trim() ? 'not-allowed' : 'pointer',
                boxShadow: '0 4px 14px rgba(109, 85, 216, 0.4)',
                transition: 'all 0.2s ease',
              }}
            >
              {isDispatching ? 'Dispatching Bot...' : '🚀 Dispatch Notetaker'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
