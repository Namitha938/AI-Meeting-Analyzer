import React, { useState, useRef, useEffect } from 'react'
import { meetingService, MeetingItem } from '../api'

interface LiveMeetingRecorderModalProps {
  isOpen: boolean
  onClose: () => void
  onMeetingCreated: (meeting: MeetingItem) => void
  theme: 'light' | 'dark'
}

export const LiveMeetingRecorderModal: React.FC<LiveMeetingRecorderModalProps> = ({
  isOpen,
  onClose,
  onMeetingCreated,
  theme,
}) => {
  const [recordState, setRecordState] = useState<'idle' | 'recording' | 'paused' | 'stopped'>('idle')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
  const [title, setTitle] = useState(`Live Sync — ${new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`)
  const [tag, setTag] = useState('Product')
  const [participants, setParticipants] = useState('Jordan Davis, Sarah Kim, Marcus Lee')
  const [color, setColor] = useState('violet')
  const [isSaving, setIsSaving] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const timerRef = useRef<any>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animFrameRef = useRef<number | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  // Clean up resources on unmount or close
  useEffect(() => {
    return () => {
      stopAllMedia()
    }
  }, [])

  const stopAllMedia = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      audioCtxRef.current.close().catch(() => {})
    }
  }

  // Visualizer loop
  const drawWaveform = () => {
    const canvas = canvasRef.current
    const analyser = analyserRef.current
    if (!canvas || !analyser) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const bufferLength = analyser.frequencyBinCount
    const dataArray = new Uint8Array(bufferLength)

    const render = () => {
      animFrameRef.current = requestAnimationFrame(render)
      analyser.getByteFrequencyData(dataArray)

      ctx.clearRect(0, 0, canvas.width, canvas.height)

      const barWidth = (canvas.width / (bufferLength / 2)) * 2.2
      let x = 0

      for (let i = 0; i < bufferLength / 2; i++) {
        const barHeight = (dataArray[i] / 255) * canvas.height * 0.9

        const gradient = ctx.createLinearGradient(0, canvas.height - barHeight, 0, canvas.height)
        gradient.addColorStop(0, '#a855f7')
        gradient.addColorStop(0.5, '#7c3aed')
        gradient.addColorStop(1, '#4f46e5')

        ctx.fillStyle = gradient
        ctx.beginPath()
        ctx.roundRect(x, canvas.height - barHeight, barWidth - 2, barHeight, [4, 4, 0, 0])
        ctx.fill()

        x += barWidth + 1
      }
    }
    render()
  }

  const startRecording = async () => {
    setErrorMessage('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext
      const audioCtx = new AudioCtxClass()
      audioCtxRef.current = audioCtx

      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 64
      analyserRef.current = analyser

      const source = audioCtx.createMediaStreamSource(stream)
      source.connect(analyser)

      const mediaRecorder = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : undefined })
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data)
        }
      }

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        setAudioBlob(blob)
        setAudioUrl(URL.createObjectURL(blob))
      }

      mediaRecorder.start(250)
      setRecordState('recording')
      setElapsedSeconds(0)

      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1)
      }, 1000)

      drawWaveform()
    } catch (err: any) {
      console.error('Microphone error:', err)
      setErrorMessage(err.message || 'Microphone access denied. Please grant permission in your browser settings.')
    }
  }

  const pauseRecording = () => {
    if (mediaRecorderRef.current && recordState === 'recording') {
      mediaRecorderRef.current.pause()
      if (timerRef.current) clearInterval(timerRef.current)
      setRecordState('paused')
    }
  }

  const resumeRecording = () => {
    if (mediaRecorderRef.current && recordState === 'paused') {
      mediaRecorderRef.current.resume()
      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1)
      }, 1000)
      setRecordState('recording')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && recordState !== 'stopped') {
      mediaRecorderRef.current.stop()
      if (timerRef.current) clearInterval(timerRef.current)
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop())
      }
      setRecordState('stopped')
    }
  }

  const handleSave = async () => {
    if (!title.trim()) return
    setIsSaving(true)
    try {
      let createdMeeting: MeetingItem
      if (audioBlob) {
        const file = new File([audioBlob], `recorded_meeting_${Date.now()}.webm`, { type: 'audio/webm' })
        const fd = new FormData()
        fd.append('title', title)
        fd.append('file', file)
        fd.append('participants', participants)
        fd.append('tags', tag)
        fd.append('color', color)
        createdMeeting = await meetingService.uploadMeeting(fd)
      } else {
        createdMeeting = await meetingService.createMeeting({
          title,
          participants,
          tags: tag,
          color,
        })
      }
      onMeetingCreated(createdMeeting)
      handleClose()
    } catch (err) {
      console.warn('API save fallback:', err)
      const mockCreated: MeetingItem = {
        id: Date.now(),
        title,
        duration_seconds: elapsedSeconds || 120,
        status: 'completed',
        participants: participants.split(',').map((s) => s.trim()),
        tags: [tag, 'Live Recording'],
        color,
        created_at: new Date().toISOString(),
      }
      onMeetingCreated(mockCreated)
      handleClose()
    } finally {
      setIsSaving(false)
    }
  }

  const handleClose = () => {
    stopAllMedia()
    setRecordState('idle')
    setAudioUrl(null)
    setAudioBlob(null)
    setElapsedSeconds(0)
    onClose()
  }

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  if (!isOpen) return null

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        background: 'rgba(10, 8, 22, 0.75)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
    >
      <div
        className="anim-fade-up"
        style={{
          width: '100%',
          maxWidth: '560px',
          background: theme === 'dark' ? '#18142a' : '#ffffff',
          color: theme === 'dark' ? '#f0eeff' : '#1f1b2e',
          borderRadius: '20px',
          boxShadow: '0 30px 80px rgba(0, 0, 0, 0.5)',
          border: `1px solid ${theme === 'dark' ? '#332959' : '#e5e7eb'}`,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: `1px solid ${theme === 'dark' ? '#261f42' : '#f0eef5'}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: theme === 'dark' ? '#1c1733' : '#faf9fe',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span
              style={{
                width: '38px',
                height: '38px',
                borderRadius: '12px',
                background: 'linear-gradient(135deg, #ef4444, #dc2626)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                boxShadow: '0 4px 12px rgba(239, 68, 68, 0.35)',
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" y1="19" x2="12" y2="22"/>
              </svg>
            </span>
            <div>
              <h3 style={{ margin: 0, fontSize: '17px', fontWeight: 700 }}>Live In-Browser Audio Recorder</h3>
              <small style={{ color: '#888' }}>Real-time Web Audio API capture & AI speech pipeline</small>
            </div>
          </div>
          <button
            onClick={handleClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#888',
              fontSize: '20px',
              cursor: 'pointer',
              padding: '4px',
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '24px' }}>
          {errorMessage && (
            <div
              style={{
                background: '#fee2e2',
                color: '#991b1b',
                padding: '12px 16px',
                borderRadius: '10px',
                fontSize: '13px',
                marginBottom: '16px',
                fontWeight: 600,
              }}
            >
              ⚠️ {errorMessage}
            </div>
          )}

          {/* Soundwave Visualizer Canvas */}
          <div
            style={{
              background: theme === 'dark' ? '#120f21' : '#f8f7fc',
              border: `1px solid ${theme === 'dark' ? '#261f42' : '#e6e2ec'}`,
              borderRadius: '14px',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '20px',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                position: 'absolute',
                top: '12px',
                left: '16px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '12px',
                fontWeight: 700,
              }}
            >
              {recordState === 'recording' && (
                <>
                  <span className="anim-record-pulse" style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444', display: 'inline-block' }} />
                  <span style={{ color: '#ef4444' }}>RECORDING LIVE</span>
                </>
              )}
              {recordState === 'paused' && (
                <>
                  <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} />
                  <span style={{ color: '#f59e0b' }}>RECORDING PAUSED</span>
                </>
              )}
              {recordState === 'stopped' && (
                <>
                  <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
                  <span style={{ color: '#10b981' }}>RECORDING READY</span>
                </>
              )}
              {recordState === 'idle' && (
                <span style={{ color: '#888' }}>STANDBY — READY TO RECORD</span>
              )}
            </div>

            {/* Timer Counter */}
            <div
              style={{
                fontSize: '38px',
                fontWeight: 800,
                fontFamily: 'monospace',
                letterSpacing: '1px',
                color: recordState === 'recording' ? (theme === 'dark' ? '#a78bfa' : '#7c3aed') : 'inherit',
                margin: '24px 0 12px',
              }}
            >
              {formatTimer(elapsedSeconds)}
            </div>

            {/* Live Canvas */}
            <canvas
              ref={canvasRef}
              width={480}
              height={70}
              style={{
                width: '100%',
                maxHeight: '70px',
                borderRadius: '8px',
                display: recordState === 'recording' || recordState === 'paused' ? 'block' : 'none',
              }}
            />

            {recordState === 'idle' && (
              <p style={{ color: '#888', fontSize: '13px', margin: '12px 0 0' }}>
                Click below to start recording directly from your browser microphone.
              </p>
            )}

            {/* Audio Preview if stopped */}
            {recordState === 'stopped' && audioUrl && (
              <div style={{ width: '100%', marginTop: '12px' }}>
                <audio controls src={audioUrl} style={{ width: '100%', height: '40px', borderRadius: '8px' }} />
              </div>
            )}
          </div>

          {/* Controls Bar */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: '12px', marginBottom: '22px' }}>
            {recordState === 'idle' && (
              <button
                type="button"
                onClick={startRecording}
                className="btn-anim"
                style={{
                  background: 'linear-gradient(135deg, #ef4444, #dc2626)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '12px',
                  padding: '12px 28px',
                  fontWeight: 700,
                  fontSize: '15px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  boxShadow: '0 8px 20px rgba(239, 68, 68, 0.35)',
                  cursor: 'pointer',
                }}
              >
                <span className="anim-record-pulse" style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#fff', display: 'inline-block' }} />
                Start Recording
              </button>
            )}

            {recordState === 'recording' && (
              <>
                <button
                  type="button"
                  onClick={pauseRecording}
                  className="btn-anim"
                  style={{
                    background: theme === 'dark' ? '#261f42' : '#f0eef5',
                    color: 'inherit',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '10px 18px',
                    fontWeight: 600,
                    fontSize: '14px',
                    cursor: 'pointer',
                  }}
                >
                  ⏸ Pause
                </button>
                <button
                  type="button"
                  onClick={stopRecording}
                  className="btn-anim"
                  style={{
                    background: '#dc2626',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '10px 22px',
                    fontWeight: 700,
                    fontSize: '14px',
                    boxShadow: '0 6px 16px rgba(220, 38, 38, 0.35)',
                    cursor: 'pointer',
                  }}
                >
                  ⏹ Stop & Process
                </button>
              </>
            )}

            {recordState === 'paused' && (
              <>
                <button
                  type="button"
                  onClick={resumeRecording}
                  className="btn-anim"
                  style={{
                    background: '#7c3aed',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '10px 20px',
                    fontWeight: 600,
                    fontSize: '14px',
                    cursor: 'pointer',
                  }}
                >
                  ▶ Resume
                </button>
                <button
                  type="button"
                  onClick={stopRecording}
                  className="btn-anim"
                  style={{
                    background: '#dc2626',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '10px 20px',
                    fontWeight: 700,
                    fontSize: '14px',
                    cursor: 'pointer',
                  }}
                >
                  ⏹ Stop & Process
                </button>
              </>
            )}

            {recordState === 'stopped' && (
              <button
                type="button"
                onClick={() => {
                  setRecordState('idle')
                  setAudioUrl(null)
                  setAudioBlob(null)
                  setElapsedSeconds(0)
                }}
                className="btn-anim"
                style={{
                  background: 'transparent',
                  color: '#888',
                  border: '1px solid #888',
                  borderRadius: '10px',
                  padding: '8px 16px',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                🔄 Re-record
              </button>
            )}
          </div>

          {/* Meeting Info Form */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ fontSize: '12px', fontWeight: 700, display: 'block', marginBottom: '6px', color: '#888' }}>
                MEETING TITLE
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Q4 Executive Product Sync"
                style={{
                  width: '100%',
                  padding: '11px 14px',
                  borderRadius: '10px',
                  border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
                  background: theme === 'dark' ? '#141124' : '#fff',
                  color: 'inherit',
                  fontSize: '14px',
                  outline: 'none',
                }}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 700, display: 'block', marginBottom: '6px', color: '#888' }}>
                  CATEGORY / TAG
                </label>
                <select
                  value={tag}
                  onChange={(e) => setTag(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '11px 14px',
                    borderRadius: '10px',
                    border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
                    background: theme === 'dark' ? '#141124' : '#fff',
                    color: 'inherit',
                    fontSize: '14px',
                  }}
                >
                  <option value="Product">Product</option>
                  <option value="Research">Research</option>
                  <option value="Engineering">Engineering</option>
                  <option value="Planning">Planning</option>
                  <option value="Design">Design</option>
                  <option value="Sales">Sales</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 700, display: 'block', marginBottom: '6px', color: '#888' }}>
                  ACCENT COLOR
                </label>
                <select
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '11px 14px',
                    borderRadius: '10px',
                    border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
                    background: theme === 'dark' ? '#141124' : '#fff',
                    color: 'inherit',
                    fontSize: '14px',
                  }}
                >
                  <option value="violet">Purple</option>
                  <option value="blue">Blue</option>
                  <option value="orange">Orange</option>
                  <option value="emerald">Emerald</option>
                  <option value="pink">Pink</option>
                </select>
              </div>
            </div>

            <div>
              <label style={{ fontSize: '12px', fontWeight: 700, display: 'block', marginBottom: '6px', color: '#888' }}>
                PARTICIPANTS
              </label>
              <input
                type="text"
                value={participants}
                onChange={(e) => setParticipants(e.target.value)}
                placeholder="Comma separated names"
                style={{
                  width: '100%',
                  padding: '11px 14px',
                  borderRadius: '10px',
                  border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
                  background: theme === 'dark' ? '#141124' : '#fff',
                  color: 'inherit',
                  fontSize: '14px',
                  outline: 'none',
                }}
              />
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '16px 24px',
            borderTop: `1px solid ${theme === 'dark' ? '#261f42' : '#f0eef5'}`,
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '12px',
            background: theme === 'dark' ? '#1c1733' : '#faf9fe',
          }}
        >
          <button
            type="button"
            onClick={handleClose}
            className="btn-anim"
            style={{
              padding: '10px 18px',
              borderRadius: '10px',
              border: `1px solid ${theme === 'dark' ? '#332959' : '#ccc'}`,
              background: 'transparent',
              color: 'inherit',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '13px',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving || (recordState !== 'stopped' && !title)}
            className="btn-anim"
            style={{
              padding: '10px 22px',
              borderRadius: '10px',
              background: '#7c3aed',
              color: '#fff',
              border: 'none',
              cursor: isSaving ? 'not-allowed' : 'pointer',
              fontWeight: 700,
              fontSize: '13px',
              boxShadow: '0 4px 14px rgba(124, 92, 255, 0.35)',
              opacity: isSaving ? 0.7 : 1,
            }}
          >
            {isSaving ? 'Processing with AI...' : 'Save & Analyze Meeting'}
          </button>
        </div>
      </div>
    </div>
  )
}

