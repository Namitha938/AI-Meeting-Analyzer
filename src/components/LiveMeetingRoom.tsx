import React, { useState, useEffect, useRef } from 'react'
import '@livekit/components-styles'
import {
  LiveKitRoom,
  RoomAudioRenderer,
} from '@livekit/components-react'
import { meetingService, LiveStatusResponse, authService, LiveParticipantItem } from '../api'
import { useRecording } from '../context/RecordingContext'

interface LiveMeetingRoomProps {
  meetingId: number
  theme: 'light' | 'dark'
  onLeave: () => void
  onMeetingEnded?: () => void
}

interface SimulatedParticipant {
  id: string
  name: string
  role: 'host' | 'participant'
  isSpeaking: boolean
  isMuted: boolean
  hasVideo: boolean
  avatarColor: string
}

export const LiveMeetingRoom: React.FC<LiveMeetingRoomProps> = ({
  meetingId,
  theme,
  onLeave,
  onMeetingEnded,
}) => {
  const { startRecordingSession, stopRecordingSession } = useRecording()
  
  // Pre-join & user profile state
  const currentUser = authService.getUser()
  const [displayName, setDisplayName] = useState<string>(
    currentUser?.full_name || currentUser?.email?.split('@')[0] || 'Meeting Participant'
  )
  const [consentChecked, setConsentChecked] = useState<boolean>(false)
  const [passcode, setPasscode] = useState<string>('')
  const [audioLevel, setAudioLevel] = useState<number>(0)
  const [handRaised, setHandRaised] = useState<boolean>(false)
  const [micEnabled, setMicEnabled] = useState<boolean>(true)
  const [camEnabled, setCamEnabled] = useState<boolean>(true)
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null)
  const [prejoinError, setPrejoinError] = useState<string | null>(null)
  const [isJoining, setIsJoining] = useState<boolean>(false)
  const [joined, setJoined] = useState<boolean>(false)

  // LiveKit connection credentials
  const [liveToken, setLiveToken] = useState<string>('')
  const [liveUrl, setLiveUrl] = useState<string>('')
  const [roomName, setRoomName] = useState<string>('')
  const [isHost, setIsHost] = useState<boolean>(false)
  const [meetingStatus, setMeetingStatus] = useState<LiveStatusResponse | null>(null)
  const [isSimulatedMode, setIsSimulatedMode] = useState<boolean>(false)
  const [roomError, setRoomError] = useState<string | null>(null)
  const isIntentionalLeaveRef = useRef<boolean>(false)

  // Zoom UI view states
  const [viewMode, setViewMode] = useState<'gallery' | 'speaker'>('gallery')
  const [activeDrawer, setActiveDrawer] = useState<'none' | 'participants' | 'chat' | 'action_items'>('none')
  const [showMeetingInfoModal, setShowMeetingInfoModal] = useState<boolean>(false)
  const [showSecurityMenu, setShowSecurityMenu] = useState<boolean>(false)
  const [showReactionsMenu, setShowReactionsMenu] = useState<boolean>(false)
  const [showEndModal, setShowEndModal] = useState<boolean>(false)
  const [activeReaction, setActiveReaction] = useState<{ emoji: string; id: number } | null>(null)
  const [screenSharing, setScreenSharing] = useState<boolean>(false)
  const [meetingDurationSec, setMeetingDurationSec] = useState<number>(0)
  const [isEndingMeeting, setIsEndingMeeting] = useState<boolean>(false)
  const [copySuccessNotice, setCopySuccessNotice] = useState<boolean>(false)
  const [pinnedParticipantId, setPinnedParticipantId] = useState<string | null>(null)

  // Phase 3: Waiting room & Moderation state
  const [isWaitingInLobby, setIsWaitingInLobby] = useState<boolean>(false)
  const [realParticipants, setRealParticipants] = useState<LiveParticipantItem[]>([])
  const [removedAlert, setRemovedAlert] = useState<boolean>(false)
  const [mutedByHostAlert, setMutedByHostAlert] = useState<boolean>(false)
  const [meetingLocked, setMeetingLocked] = useState<boolean>(false)

  // Phase 6: Live Captions & Live Action Items State
  const isSpeechRecognitionSupported = typeof window !== 'undefined' && Boolean((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)
  const [captionConsentGiven, setCaptionConsentGiven] = useState<boolean>(() => {
    return typeof window !== 'undefined' && localStorage.getItem('meetora_caption_consent') === 'true'
  })
  const [captionsEnabled, setCaptionsEnabled] = useState<boolean>(false)
  const [showCaptionConsentModal, setShowCaptionConsentModal] = useState<boolean>(false)
  const [activeCaption, setActiveCaption] = useState<string | null>(null)
  const [activeCaptionSpeaker, setActiveCaptionSpeaker] = useState<string | null>(null)
  const [liveActionItems, setLiveActionItems] = useState<Array<{
    id: number
    title: string
    assignee?: string | null
    deadline?: string | null
    status: string
    confidence_score?: number
    context_quote?: string
  }>>([])
  const [newActionItemTitle, setNewActionItemTitle] = useState<string>('')
  const [newActionItemAssignee, setNewActionItemAssignee] = useState<string>('')
  const [newActionItemDeadline, setNewActionItemDeadline] = useState<string>('')
  const [actionItemToast, setActionItemToast] = useState<string | null>(null)
  const [chatInput, setChatInput] = useState<string>('')
  const [chatRecipient, setChatRecipient] = useState<string>('Everyone')
  const [chatMessages, setChatMessages] = useState<Array<{ sender: string; recipient?: string; text: string; time: string; isSelf?: boolean }>>([
    { sender: 'Zoom System', recipient: 'Everyone', text: 'Welcome to Zoom Meeting. Cloud recording & AI transcription enabled.', time: 'Just now' }
  ])

  // Simulated Zoom Participants
  const [simulatedParticipants, setSimulatedParticipants] = useState<SimulatedParticipant[]>([
    { id: 'p1', name: displayName, role: 'host', isSpeaking: false, isMuted: false, hasVideo: true, avatarColor: '#0e72ed' },
    { id: 'p2', name: 'Sarah Kim', role: 'participant', isSpeaking: true, isMuted: false, hasVideo: true, avatarColor: '#ec4899' },
    { id: 'p3', name: 'Marcus Lee', role: 'participant', isSpeaking: false, isMuted: true, hasVideo: false, avatarColor: '#10b981' },
    { id: 'p4', name: 'Alex Lin', role: 'participant', isSpeaking: false, isMuted: false, hasVideo: true, avatarColor: '#f59e0b' },
  ])

  // Zoom Recording States & Refs
  const [isRecording, setIsRecording] = useState<boolean>(false)
  const [recordingDurationSec, setRecordingDurationSec] = useState<number>(0)
  const [isRecordingLoading, setIsRecordingLoading] = useState<boolean>(false)
  const [uploadProgressMsg, setUploadProgressMsg] = useState<string | null>(null)
  const [localRecordingUrl, setLocalRecordingUrl] = useState<string | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const recordedChunksRef = useRef<Blob[]>([])
  const screenStreamRef = useRef<MediaStream | null>(null)

  const prejoinVideoRef = useRef<HTMLVideoElement | null>(null)
  const localVideoRef = useRef<HTMLVideoElement | null>(null)

  // Stop all active media tracks when component unmounts
  useEffect(() => {
    return () => {
      stopAllMedia()
    }
  }, [])

  // Attach camera stream to local video in Zoom room
  useEffect(() => {
    if (joined && camEnabled && localVideoRef.current && cameraStream) {
      localVideoRef.current.srcObject = cameraStream
    }
  }, [joined, camEnabled, cameraStream])

  // Re-acquire camera stream if needed when entering Zoom room
  useEffect(() => {
    if (joined && camEnabled && !cameraStream && navigator.mediaDevices?.getUserMedia) {
      navigator.mediaDevices.getUserMedia({ video: true, audio: micEnabled })
        .then((stream) => {
          setCameraStream(stream)
          if (localVideoRef.current) {
            localVideoRef.current.srcObject = stream
          }
        })
        .catch((err) => console.warn('Could not re-acquire camera stream in room:', err))
    }
  }, [joined, camEnabled])

  // Captions Handler
  const handleNewCaption = async (speaker: string, captionText: string) => {
    setActiveCaption(captionText)
    setActiveCaptionSpeaker(speaker)
    setTimeout(() => {
      setActiveCaption((curr) => (curr === captionText ? null : curr))
    }, 4500)

    try {
      const res = await meetingService.sendLiveCaption(meetingId, {
        text: captionText,
        speaker,
        timestamp: meetingDurationSec,
      })
      if (res.detected_action_item) {
        const item = res.detected_action_item
        setLiveActionItems((prev) => [
          ...prev,
          {
            id: Date.now(),
            title: item.title,
            assignee: item.assignee,
            deadline: item.deadline,
            status: 'suggested',
            confidence_score: item.confidence_score,
            context_quote: item.context_quote,
          },
        ])
        setActionItemToast(`⚡ AI Action Item Detected: "${item.title}" (${item.assignee || 'Assigned'})`)
        setTimeout(() => setActionItemToast(null), 5000)
      }
    } catch (e) {
      console.warn('Caption notice:', e)
    }
  }

  // Load existing action items on join
  useEffect(() => {
    if (!joined) return
    meetingService.getLiveActionItems(meetingId).then((items) => {
      if (items && items.length > 0) {
        setLiveActionItems(items as any)
      }
    }).catch(() => {})
  }, [joined, meetingId])

  // Simulated dialogue captions for preview / demo mode
  useEffect(() => {
    if (!joined || !captionsEnabled) return
    const timer1 = setTimeout(() => {
      handleNewCaption('Sarah Kim', 'I will finalize the technical architecture specification by Friday.')
    }, 7000)

    const timer2 = setTimeout(() => {
      handleNewCaption('Marcus Lee', 'Let us review the API changes with the backend team tomorrow.')
    }, 18000)

    return () => {
      clearTimeout(timer1)
      clearTimeout(timer2)
    }
  }, [joined, captionsEnabled])

  // Real in-browser Web Speech API recognition when user speaks
  useEffect(() => {
    if (!joined || !micEnabled || !captionsEnabled) return
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRecognition) return

    let rec: any
    try {
      rec = new SpeechRecognition()
      rec.continuous = true
      rec.interimResults = false
      rec.lang = 'en-US'
      rec.onresult = (evt: any) => {
        const last = evt.results[evt.results.length - 1]
        if (last && last[0] && last[0].transcript) {
          const text = last[0].transcript.trim()
          if (text) {
            handleNewCaption(displayName, text)
          }
        }
      }
      rec.onerror = (e: any) => console.warn('Speech recognition warning:', e)
      rec.start()
    } catch (e) {
      console.warn('Could not start speech recognition:', e)
    }

    return () => {
      if (rec) {
        try { rec.stop() } catch {}
      }
    }
  }, [joined, micEnabled, captionsEnabled, displayName, meetingId, meetingDurationSec])

  // Poll real participants and waiting status if host or in waiting room
  const refreshParticipants = () => {
    meetingService.getLiveParticipants(meetingId)
      .then(setRealParticipants)
      .catch(() => {})
  }

  useEffect(() => {
    if (!joined && !isWaitingInLobby) return
    refreshParticipants()
    const pInterval = setInterval(refreshParticipants, 3000)
    return () => clearInterval(pInterval)
  }, [joined, isWaitingInLobby, meetingId])

  // Waiting room lobby status check
  useEffect(() => {
    if (!isWaitingInLobby) return
    const pollTimer = setInterval(async () => {
      try {
        const st = await meetingService.getWaitingStatus(meetingId)
        if (st.status === 'admitted' && st.token) {
          setLiveToken(st.token)
          setLiveUrl(st.livekit_url)
          setRoomName(st.room_name)
          setIsHost(st.is_host)
          setIsWaitingInLobby(false)
          setJoined(true)
        } else if (st.status === 'denied') {
          alert('The host has denied your admission to this meeting.')
          onLeave()
        } else if (st.status === 'removed') {
          setRemovedAlert(true)
          setIsWaitingInLobby(false)
        }
      } catch (e) {
        console.warn('Waiting room status check error:', e)
      }
    }, 2500)
    return () => clearInterval(pollTimer)
  }, [isWaitingInLobby, meetingId])

  // Fetch meeting live status on mount and poll periodically
  useEffect(() => {
    let mounted = true
    const checkStatus = () => {
      meetingService.getLiveMeetingStatus(meetingId)
        .then((st) => {
          if (mounted) {
            setMeetingStatus(st)
            setIsHost(st.is_host)
            if (st.live_status === 'ended' && !isIntentionalLeaveRef.current) {
              isIntentionalLeaveRef.current = true
              stopAllMedia()
              if (onMeetingEnded) {
                onMeetingEnded()
              } else {
                onLeave()
              }
              return
            }
            if (st.live_status === 'recording' && !isRecording) {
              setIsRecording(true)
            } else if (st.live_status === 'live' && isRecording) {
              setIsRecording(false)
            }
          }
        })
        .catch((err) => {
          console.warn('Could not fetch live meeting status:', err)
          const status = err?.response?.status
          const detail = err?.response?.data?.detail
          if (status === 401) {
            authService.clearSession()
            window.location.hash = 'login?expired=session'
          } else if (status) {
            setPrejoinError(`[HTTP ${status}]: ${typeof detail === 'string' ? detail : 'Could not fetch live meeting status'}`)
          }
        })
    }
    checkStatus()
    const interval = setInterval(checkStatus, 4000)
    return () => {
      mounted = false
      clearInterval(interval)
    }
  }, [meetingId, isRecording])

  // Recording timer
  useEffect(() => {
    if (!isRecording) {
      setRecordingDurationSec(0)
      return
    }
    const timer = setInterval(() => {
      setRecordingDurationSec((prev) => prev + 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [isRecording])

  // CORE RECORDING HANDLERS (ZOOM STYLE RECORDING CAPTURE & UPLOAD)
  const handleStartRecording = async () => {
    setIsRecordingLoading(true)
    try {
      await meetingService.startLiveRecording(meetingId).catch((e) => console.warn('Backend start recording:', e))
      setIsRecording(true)

      // Start browser MediaRecorder as high-fidelity video & audio capture
      try {
        let streamToRecord: MediaStream | null = cameraStream
        if (!streamToRecord && navigator.mediaDevices?.getUserMedia) {
          streamToRecord = await navigator.mediaDevices.getUserMedia({
            video: camEnabled,
            audio: true,
          }).catch(() => null)
        }
        if (streamToRecord) {
          const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus')
            ? 'video/webm;codecs=vp9,opus'
            : MediaRecorder.isTypeSupported('video/webm')
            ? 'video/webm'
            : 'audio/webm'
          const recorder = new MediaRecorder(streamToRecord, { mimeType })
          recordedChunksRef.current = []
          recorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) {
              recordedChunksRef.current.push(e.data)
            }
          }
          recorder.start(1000)
          mediaRecorderRef.current = recorder
        }
      } catch (recErr) {
        console.warn('Browser MediaRecorder stream capture:', recErr)
      }
    } catch (err: any) {
      alert(err?.message || 'Failed to start live recording')
    } finally {
      setIsRecordingLoading(false)
    }
  }

  const handleStopRecording = async () => {
    setIsRecordingLoading(true)
    try {
      // If browser MediaRecorder was running, package into 5MB chunks and upload
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        const recorder = mediaRecorderRef.current
        await new Promise<void>((resolve) => {
          recorder.onstop = () => resolve()
          recorder.stop()
        })
        const fullBlob = new Blob(recordedChunksRef.current, { type: recorder.mimeType || 'video/webm' })
        if (fullBlob.size > 0) {
          try {
            const blobUrl = URL.createObjectURL(fullBlob)
            setLocalRecordingUrl(blobUrl)
          } catch (_) {}
          const CHUNK_SIZE = 5 * 1024 * 1024 // 5 MB chunks
          const totalChunks = Math.max(1, Math.ceil(fullBlob.size / CHUNK_SIZE))
          setUploadProgressMsg(`Saving Zoom recording (${totalChunks} parts)...`)
          for (let i = 0; i < totalChunks; i++) {
            const start = i * CHUNK_SIZE
            const end = Math.min(fullBlob.size, start + CHUNK_SIZE)
            const chunkBlob = fullBlob.slice(start, end)
            setUploadProgressMsg(`Uploading recording part ${i + 1}/${totalChunks}...`)
            await meetingService.uploadRecordingChunk(
              meetingId,
              chunkBlob,
              i,
              totalChunks,
              'composite_video'
            )
          }
        }
      }

      await meetingService.stopLiveRecording(meetingId).catch(() => {})
      // Trigger AI analysis pipeline to produce executive summary, tasks, diarization, chapters, and score
      await meetingService.analyzeMeeting(meetingId).catch(() => {})
      setUploadProgressMsg('Recording saved! Meetora AI is analyzing executive summary, tasks, diarization, chapters, and score...')
      setTimeout(() => setUploadProgressMsg(null), 6000)
      setIsRecording(false)
      stopRecordingSession()
    } catch (err: any) {
      alert(err?.message || 'Failed to stop live recording')
    } finally {
      setIsRecordingLoading(false)
    }
  }

  const stopAllMedia = () => {
    try {
      if (cameraStream) {
        cameraStream.getTracks().forEach((track) => track.stop())
        setCameraStream(null)
      }
      if (screenStreamRef.current) {
        screenStreamRef.current.getTracks().forEach((track) => track.stop())
        screenStreamRef.current = null
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try { mediaRecorderRef.current.stop() } catch (_) {}
      }
      if (localVideoRef.current) {
        localVideoRef.current.srcObject = null
      }
      if (prejoinVideoRef.current) {
        prejoinVideoRef.current.srcObject = null
      }
    } catch (e) {
      console.warn('Error stopping media devices:', e)
    }
  }

  const stopPreviewMedia = stopAllMedia

  const handleSafeLeave = async () => {
    isIntentionalLeaveRef.current = true
    setIsEndingMeeting(true)
    setShowEndModal(false)

    try {
      if (isRecording) {
        const confirmSave = window.confirm(
          'A Zoom recording is in progress. Would you like to stop and save the recording before leaving?'
        )
        if (confirmSave) {
          await handleStopRecording()
        } else {
          if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            try { mediaRecorderRef.current.stop() } catch (_) {}
          }
          await meetingService.stopLiveRecording(meetingId).catch(() => {})
          setIsRecording(false)
          stopRecordingSession()
        }
      }

      await meetingService.leaveLiveMeeting(meetingId).catch(() => {})
    } catch (err: any) {
      console.warn('Safe leave warning:', err)
    } finally {
      stopAllMedia()
      setIsEndingMeeting(false)
      onLeave()
    }
  }

  // Pre-join camera preview
  useEffect(() => {
    if (!joined && camEnabled) {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ video: true, audio: micEnabled })
          .then((stream) => {
            setCameraStream(stream)
            if (prejoinVideoRef.current) {
              prejoinVideoRef.current.srcObject = stream
            }

            // Web Audio API Audio Level Meter
            if (micEnabled && stream.getAudioTracks().length > 0) {
              try {
                const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
                if (AudioCtx) {
                  const audioCtx = new AudioCtx()
                  const analyser = audioCtx.createAnalyser()
                  analyser.fftSize = 64
                  const micSource = audioCtx.createMediaStreamSource(stream)
                  micSource.connect(analyser)
                  const pcmData = new Uint8Array(analyser.frequencyBinCount)

                  let animFrame: number
                  const measure = () => {
                    analyser.getByteFrequencyData(pcmData)
                    let total = 0
                    for (let i = 0; i < pcmData.length; i++) total += pcmData[i]
                    const avg = total / pcmData.length
                    setAudioLevel(Math.min(100, Math.round((avg / 128) * 100)))
                    animFrame = requestAnimationFrame(measure)
                  }
                  measure()

                  return () => {
                    cancelAnimationFrame(animFrame)
                    audioCtx.close().catch(() => {})
                  }
                }
              } catch (audioErr) {
                console.warn('Microphone level meter not available:', audioErr)
              }
            }
          })
          .catch((err) => {
            console.warn('Camera preview not accessible:', err)
          })
      }
    } else if (!joined) {
      if (cameraStream) {
        cameraStream.getTracks().forEach((track) => track.stop())
        setCameraStream(null)
      }
    }
  }, [joined, camEnabled])

  // Active meeting timer
  useEffect(() => {
    if (!joined) return
    const timer = setInterval(() => {
      setMeetingDurationSec((prev) => prev + 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [joined])

  // Periodic random speaking activity for simulated teammates
  useEffect(() => {
    if (!joined || !isSimulatedMode) return
    const speakerInterval = setInterval(() => {
      setSimulatedParticipants((prev) =>
        prev.map((p) => {
          if (p.isMuted) return { ...p, isSpeaking: false }
          return { ...p, isSpeaking: Math.random() > 0.65 }
        })
      )
    }, 2800)
    return () => clearInterval(speakerInterval)
  }, [joined, isSimulatedMode])

  // Zoom Screen Share Toggle
  const handleToggleScreenShare = async () => {
    if (screenSharing) {
      if (screenStreamRef.current) {
        screenStreamRef.current.getTracks().forEach((track) => track.stop())
        screenStreamRef.current = null
      }
      setScreenSharing(false)
    } else {
      try {
        if (navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) {
          const displayStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true })
          screenStreamRef.current = displayStream
          setScreenSharing(true)
          displayStream.getVideoTracks()[0].onended = () => {
            if (screenStreamRef.current) {
              screenStreamRef.current.getTracks().forEach((track) => track.stop())
              screenStreamRef.current = null
            }
            setScreenSharing(false)
          }
        } else {
          setScreenSharing(true)
        }
      } catch {
        setScreenSharing(false)
      }
    }
  }

  // Keyboard Shortcuts (M, V, S, C, P, R)
  useEffect(() => {
    if (!joined) return
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      if (
        target?.tagName === 'INPUT' ||
        target?.tagName === 'TEXTAREA' ||
        target?.isContentEditable
      ) {
        return
      }

      const key = e.key.toUpperCase()
      if (key === 'M') {
        e.preventDefault()
        setMicEnabled((prev) => !prev)
      } else if (key === 'V') {
        e.preventDefault()
        setCamEnabled((prev) => !prev)
      } else if (key === 'S') {
        e.preventDefault()
        handleToggleScreenShare()
      } else if (key === 'C') {
        e.preventDefault()
        setActiveDrawer((prev) => (prev === 'chat' ? 'none' : 'chat'))
      } else if (key === 'P') {
        e.preventDefault()
        setActiveDrawer((prev) => (prev === 'participants' ? 'none' : 'participants'))
      } else if (key === 'R') {
        e.preventDefault()
        if (isRecording) {
          handleStopRecording()
        } else {
          handleStartRecording()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [joined, isRecording, screenSharing, camEnabled, micEnabled])

  // Join handler
  const handleJoinMeeting = async () => {
    if (!consentChecked) {
      setPrejoinError('You must check the consent box to proceed.')
      return
    }
    if (!displayName.trim()) {
      setPrejoinError('Please enter your display name.')
      return
    }

    setPrejoinError(null)
    setIsJoining(true)

    try {
      const joinData = await meetingService.joinLiveMeeting(meetingId, {
        display_name: displayName.trim(),
        consent: true,
        passcode: passcode.trim() || undefined,
      })

      if (joinData.status === 'waiting') {
        setIsWaitingInLobby(true)
        setIsJoining(false)
        return
      }

      setLiveToken(joinData.token)
      setLiveUrl(joinData.livekit_url)
      setRoomName(joinData.room_name)
      setIsHost(joinData.is_host)

      const hasRealLiveKitUrl = Boolean(
        joinData.livekit_url &&
        !joinData.livekit_url.includes('your-project') &&
        joinData.livekit_url.startsWith('ws')
      )

      if (hasRealLiveKitUrl) {
        setIsSimulatedMode(false)
      } else {
        setIsSimulatedMode(true)
      }

      setJoined(true)
    } catch (err: any) {
      console.warn('Failed to join live meeting via API:', err)
      const status = err?.response?.status
      const detail = err?.response?.data?.detail || err?.message || 'Failed to join live meeting'

      if (status === 401) {
        authService.clearSession()
        window.location.hash = 'login?expired=session'
        return
      }

      const errorMsg = status
        ? `[HTTP ${status}]: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`
        : (typeof detail === 'string' ? detail : 'Failed to join live meeting')
      setPrejoinError(errorMsg)
    } finally {
      setIsJoining(false)
    }
  }

  // End meeting (Host or caller)
  const handleEndMeeting = async () => {
    isIntentionalLeaveRef.current = true
    setIsEndingMeeting(true)
    setShowEndModal(false)

    try {
      if (isRecording) {
        await handleStopRecording()
      } else {
        await meetingService.analyzeMeeting(meetingId).catch(() => {})
      }

      // Attempt host end live meeting endpoint, fallback to leave
      await meetingService.endLiveMeeting(meetingId).catch(async (err) => {
        console.warn('Backend end live meeting warning (falling back to leave):', err)
        return meetingService.leaveLiveMeeting(meetingId).catch(() => ({}))
      })
    } catch (err: any) {
      console.warn('Error during end live meeting (finishing cleanup):', err)
    } finally {
      stopAllMedia()
      setIsEndingMeeting(false)
      if (onMeetingEnded) {
        onMeetingEnded()
      } else {
        onLeave()
      }
    }
  }

  // Send Zoom Chat message
  const handleSendChat = (e: React.FormEvent) => {
    e.preventDefault()
    if (!chatInput.trim()) return
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    setChatMessages((prev) => [
      ...prev,
      { sender: displayName, recipient: chatRecipient, text: chatInput.trim(), time: now, isSelf: true }
    ])
    setChatInput('')
  }

  // Trigger Reaction
  const handleTriggerReaction = (emoji: string) => {
    setActiveReaction({ emoji, id: Date.now() })
    setShowReactionsMenu(false)
    setTimeout(() => {
      setActiveReaction(null)
    }, 3800)
  }

  // Copy meeting invite link
  const handleCopyInviteLink = () => {
    const url = `${window.location.origin}/#live/${meetingId}`
    navigator.clipboard.writeText(url)
    setCopySuccessNotice(true)
    setTimeout(() => setCopySuccessNotice(false), 3000)
  }

  const formatTimer = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60)
    const secs = totalSeconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  // =========================================================================
  // 1. WAITING ROOM SCREEN
  // =========================================================================
  if (isWaitingInLobby) {
    return (
      <div
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 99999,
          background: '#121214',
          color: '#ffffff',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        }}
      >
        <div
          style={{
            maxWidth: '460px',
            width: '100%',
            textAlign: 'center',
            background: '#1f1f23',
            borderRadius: '16px',
            padding: '36px',
            boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
            border: '1px solid #2d2d34',
          }}
        >
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>⏳</div>
          <h2 style={{ fontSize: '20px', fontWeight: 700, margin: '0 0 10px', color: '#fff' }}>Please wait, the meeting host will let you in soon.</h2>
          <p style={{ fontSize: '13px', color: '#9ca3af', lineHeight: '1.5', margin: '0 0 24px' }}>
            Meeting: <strong>{roomName || `Weekly meet #${meetingId}`}</strong>
          </p>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: '#0e72ed', background: 'rgba(14, 114, 237, 0.15)', padding: '6px 14px', borderRadius: '16px', fontSize: '12px', fontWeight: 600, marginBottom: '24px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#0e72ed', animation: 'pulse 1.5s infinite' }} />
            Waiting for host to admit you...
          </div>
          <div>
            <button
              type="button"
              onClick={handleSafeLeave}
              style={{
                background: '#374151',
                color: '#fff',
                border: 'none',
                padding: '8px 24px',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Leave Meeting
            </button>
          </div>
        </div>
      </div>
    )
  }

  // =========================================================================
  // 2. PRE-JOIN / DEVICE CHECK SCREEN (ZOOM PRE-JOIN LOBBY)
  // =========================================================================
  if (!joined) {
    return (
      <div
        className="zoom-prejoin-container"
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 99999,
          background: '#0e0e11',
          color: '#ffffff',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          overflowY: 'auto',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        }}
      >
        <div
          style={{
            width: '100%',
            maxWidth: '560px',
            background: '#18181b',
            borderRadius: '16px',
            padding: '32px',
            boxShadow: '0 25px 60px rgba(0,0,0,0.6)',
            border: '1px solid #27272a',
          }}
        >
          {/* Zoom Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ width: '32px', height: '32px', background: '#0e72ed', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '18px' }}>
                📹
              </div>
              <div>
                <h2 style={{ fontSize: '18px', margin: 0, fontWeight: 700, color: '#fff' }}>Zoom Meeting Preview</h2>
                <span style={{ fontSize: '11px', color: '#9ca3af' }}>Check your camera and microphone before joining</span>
              </div>
            </div>
            <button
              onClick={handleSafeLeave}
              style={{
                background: 'transparent',
                border: 'none',
                fontSize: '18px',
                cursor: 'pointer',
                color: '#9ca3af',
                padding: '6px',
              }}
              title="Cancel and return"
            >
              ✕
            </button>
          </div>

          {/* Camera Preview Tile */}
          <div
            style={{
              position: 'relative',
              width: '100%',
              height: '240px',
              background: '#09090b',
              borderRadius: '12px',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '20px',
              border: '2px solid #27272a',
            }}
          >
            {camEnabled ? (
              <video
                ref={prejoinVideoRef}
                autoPlay
                playsInline
                muted
                style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)' }}
              />
            ) : (
              <div style={{ textAlign: 'center', color: '#a1a1aa' }}>
                <div style={{ width: '70px', height: '70px', borderRadius: '50%', background: '#0e72ed', color: '#fff', fontSize: '26px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
                  {displayName.slice(0, 2).toUpperCase() || 'ME'}
                </div>
                <p style={{ margin: 0, fontSize: '13px' }}>Camera is turned off</p>
              </div>
            )}

            {/* Audio Level Meter */}
            {micEnabled && (
              <div
                style={{
                  position: 'absolute',
                  top: '12px',
                  left: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: 'rgba(0,0,0,0.7)',
                  backdropFilter: 'blur(6px)',
                  padding: '4px 10px',
                  borderRadius: '12px',
                }}
              >
                <span style={{ fontSize: '11px' }}>🎤</span>
                <div style={{ width: '50px', height: '6px', background: '#27272a', borderRadius: '3px', overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      width: `${audioLevel}%`,
                      background: audioLevel > 50 ? '#22c55e' : '#0e72ed',
                      transition: 'width 0.1s ease',
                    }}
                  />
                </div>
              </div>
            )}

            {/* Preview device controls */}
            <div
              style={{
                position: 'absolute',
                bottom: '12px',
                left: '50%',
                transform: 'translateX(-50%)',
                display: 'flex',
                gap: '12px',
                background: 'rgba(24, 24, 27, 0.85)',
                backdropFilter: 'blur(8px)',
                padding: '6px 14px',
                borderRadius: '24px',
                border: '1px solid #3f3f46',
              }}
            >
              <button
                type="button"
                onClick={() => setMicEnabled((prev) => !prev)}
                style={{
                  background: micEnabled ? '#27272a' : '#ef4444',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '50%',
                  width: '38px',
                  height: '38px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  fontSize: '15px',
                }}
                title={micEnabled ? 'Mute Mic' : 'Unmute Mic'}
              >
                {micEnabled ? '🎤' : '🔇'}
              </button>

              <button
                type="button"
                onClick={() => setCamEnabled((prev) => !prev)}
                style={{
                  background: camEnabled ? '#27272a' : '#ef4444',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '50%',
                  width: '38px',
                  height: '38px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  fontSize: '15px',
                }}
                title={camEnabled ? 'Stop Video' : 'Start Video'}
              >
                {camEnabled ? '📹' : '🚫'}
              </button>
            </div>
          </div>

          {/* Form Fields */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {meetingStatus?.live_status === 'recording' && (
              <div
                style={{
                  background: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid #ef4444',
                  borderRadius: '10px',
                  padding: '12px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                }}
              >
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444', display: 'inline-block' }} />
                <div>
                  <b style={{ color: '#ef4444', fontSize: '13px' }}>🔴 Recording in Progress</b>
                  <p style={{ margin: '2px 0 0', fontSize: '11px', color: '#a1a1aa' }}>
                    This meeting is currently being recorded. By joining, your audio & video will be included in the AI transcript and summary.
                  </p>
                </div>
              </div>
            )}

            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, marginBottom: '6px', color: '#d4d4d8' }}>
                Your Name
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. Jordan Davis"
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid #3f3f46',
                  background: '#27272a',
                  color: '#fff',
                  fontSize: '13px',
                }}
              />
            </div>

            {meetingStatus?.has_passcode && (
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, marginBottom: '6px', color: '#d4d4d8' }}>
                  Meeting Passcode
                </label>
                <input
                  type="password"
                  value={passcode}
                  onChange={(e) => setPasscode(e.target.value)}
                  placeholder="Enter meeting passcode"
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    border: '1px solid #3f3f46',
                    background: '#27272a',
                    color: '#fff',
                    fontSize: '13px',
                  }}
                />
              </div>
            )}

            {/* MANDATORY RECORDING CONSENT */}
            <div
              style={{
                background: 'rgba(14, 114, 237, 0.08)',
                border: `1px solid ${consentChecked ? '#0e72ed' : '#27272a'}`,
                borderRadius: '10px',
                padding: '14px',
                transition: 'all 0.2s ease',
              }}
            >
              <label
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '12px',
                  cursor: 'pointer',
                  fontSize: '13px',
                  lineHeight: '1.4',
                }}
              >
                <input
                  type="checkbox"
                  checked={consentChecked}
                  onChange={(e) => {
                    setConsentChecked(e.target.checked)
                    if (e.target.checked) setPrejoinError(null)
                  }}
                  style={{
                    width: '18px',
                    height: '18px',
                    marginTop: '2px',
                    accentColor: '#0e72ed',
                    cursor: 'pointer',
                  }}
                />
                <div>
                  <span style={{ fontWeight: 600, color: consentChecked ? '#38bdf8' : '#e4e4e7' }}>
                    I consent to meeting recording and AI analysis
                  </span>
                  <small style={{ display: 'block', color: '#a1a1aa', marginTop: '4px', fontSize: '11px' }}>
                    Enables real-time speaker transcription, recording archives, action item detection, and automatic executive summaries.
                  </small>
                </div>
              </label>
            </div>

            {prejoinError && (
              <div style={{
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                borderRadius: '8px',
                padding: '12px 14px',
                color: '#ef4444',
                fontSize: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
                  <span style={{ fontSize: '16px' }}>⚠️</span>
                  <span>{prejoinError}</span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    if (cameraStream) {
                      cameraStream.getTracks().forEach((track) => track.stop())
                      setCameraStream(null)
                    }
                    setIsSimulatedMode(true)
                    setJoined(true)
                  }}
                  className="button small"
                  style={{
                    alignSelf: 'flex-start',
                    background: '#0e72ed',
                    color: '#fff',
                    border: 'none',
                    fontSize: '11px',
                    padding: '7px 14px',
                    fontWeight: 600,
                    borderRadius: '6px',
                    cursor: 'pointer',
                  }}
                >
                  🎮 Enter in Zoom Practice Mode
                </button>
              </div>
            )}

            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
              <button
                type="button"
                onClick={handleSafeLeave}
                style={{
                  flex: 1,
                  padding: '12px',
                  background: '#27272a',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 600,
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleJoinMeeting}
                disabled={!consentChecked || isJoining}
                style={{
                  flex: 2,
                  padding: '12px 20px',
                  background: '#0e72ed',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 700,
                  fontSize: '13px',
                  opacity: (!consentChecked || isJoining) ? 0.5 : 1,
                  cursor: (!consentChecked || isJoining) ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                {isJoining ? 'Joining Meeting...' : 'Join Meeting Now'}
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // =========================================================================
  // 3. TRUE ZOOM MEETING APP INTERFACE (MAIN IN-CALL SCREEN)
  // =========================================================================
  const zoomMeetingContent = (
    <div
      className="zoom-app-fullscreen"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 99999,
        background: '#121214',
        color: '#ffffff',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        userSelect: 'none',
      }}
    >
      {/* ================= ZOOM HEADER BAR ================= */}
      <div
        style={{
          height: '48px',
          background: '#18181b',
          borderBottom: '1px solid #27272a',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
        }}
      >
        {/* Left: Security Info Shield & Recording Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            type="button"
            onClick={() => setShowMeetingInfoModal((prev) => !prev)}
            style={{
              background: 'transparent',
              border: 'none',
              padding: '6px',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              color: '#22c55e',
            }}
            title="Meeting Information (Encryption & ID)"
          >
            <span style={{ fontSize: '16px' }}>🛡️</span>
            <span style={{ fontSize: '11px', color: '#a1a1aa', fontWeight: 600 }}>Zoom Info</span>
          </button>

          {/* ACTIVE ZOOM RECORDING BADGE */}
          {isRecording && (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                background: 'rgba(239, 68, 68, 0.2)',
                border: '1px solid #ef4444',
                borderRadius: '16px',
                padding: '3px 10px',
                fontSize: '11px',
                fontWeight: 700,
                color: '#ef4444',
              }}
            >
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: '#ef4444',
                  display: 'inline-block',
                  boxShadow: '0 0 8px #ef4444',
                }}
              />
              <span>REC {formatTimer(recordingDurationSec)}</span>
              <span style={{ fontSize: '10px', opacity: 0.8, color: '#fca5a5' }}>• Cloud Recording</span>
            </div>
          )}
        </div>

        {/* Center: Meeting Topic & Duration */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#e4e4e7' }}>
            {roomName || meetingStatus?.title || `Weekly meet #${meetingId}`}
          </span>
          <span style={{ fontSize: '11px', color: '#71717a' }}>•</span>
          <span style={{ fontSize: '12px', color: '#a1a1aa' }}>
            {formatTimer(meetingDurationSec)}
          </span>
        </div>

        {/* Right: View Switcher (Gallery vs Speaker) & Fullscreen */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            onClick={() => setViewMode((prev) => (prev === 'gallery' ? 'speaker' : 'gallery'))}
            style={{
              background: '#27272a',
              border: 'none',
              borderRadius: '6px',
              padding: '6px 12px',
              fontSize: '11px',
              fontWeight: 600,
              color: '#d4d4d8',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>{viewMode === 'gallery' ? '👤 Speaker View' : '🖼️ Gallery View'}</span>
          </button>
        </div>
      </div>

      {/* ================= ZOOM MAIN VIDEO STAGE & DRAWERS ================= */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        {/* Connection Error Banner (if LiveKit drops) */}
        {roomError && (
          <div
            style={{
              position: 'absolute',
              top: '16px',
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 90,
              background: '#ef4444',
              color: '#fff',
              padding: '10px 18px',
              borderRadius: '8px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            <span>⚠️ {roomError}</span>
            <button
              type="button"
              onClick={() => {
                setRoomError(null)
                setIsSimulatedMode(true)
              }}
              style={{
                background: '#fff',
                color: '#ef4444',
                border: 'none',
                borderRadius: '6px',
                padding: '4px 10px',
                fontSize: '11px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Continue in Practice Mode
            </button>
          </div>
        )}

        {/* Floating Zoom Reaction Animation */}
        {activeReaction && (
          <div
            style={{
              position: 'absolute',
              bottom: '100px',
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 80,
              fontSize: '48px',
              pointerEvents: 'none',
              animation: 'bounce 1s ease-in-out infinite',
            }}
          >
            {activeReaction.emoji}
          </div>
        )}

        {/* Floating Closed Captions Overlay */}
        {captionsEnabled && activeCaption && (
          <div
            style={{
              position: 'absolute',
              bottom: '24px',
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 70,
              background: 'rgba(0, 0, 0, 0.85)',
              backdropFilter: 'blur(8px)',
              color: '#ffffff',
              padding: '10px 20px',
              borderRadius: '8px',
              border: '1px solid #3f3f46',
              boxShadow: '0 8px 30px rgba(0,0,0,0.6)',
              maxWidth: '85%',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              fontSize: '13px',
            }}
          >
            <span style={{ background: '#0e72ed', color: '#fff', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700 }}>
              {activeCaptionSpeaker || 'Speaker'}
            </span>
            <span>"{activeCaption}"</span>
          </div>
        )}

        {/* Screen Sharing Stage (Zoom presentation mode) */}
        {screenSharing ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#09090b', padding: '16px', position: 'relative' }}>
            <div style={{ background: '#22c55e', color: '#000', padding: '6px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: 700, alignSelf: 'center', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>🖥️ You are sharing screen</span>
              <button
                type="button"
                onClick={() => setScreenSharing(false)}
                style={{ background: '#000', color: '#fff', border: 'none', borderRadius: '4px', padding: '2px 8px', fontSize: '11px', cursor: 'pointer', fontWeight: 600 }}
              >
                Stop Share
              </button>
            </div>
            <div
              style={{
                flex: 1,
                background: '#18181b',
                borderRadius: '12px',
                border: '2px dashed #0e72ed',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '24px',
              }}
            >
              <div style={{ fontSize: '56px', marginBottom: '16px' }}>📊</div>
              <h3 style={{ margin: '0 0 8px', fontSize: '18px', color: '#fff' }}>Meetora AI Meeting Analyzer Presentation</h3>
              <p style={{ margin: 0, fontSize: '13px', color: '#a1a1aa' }}>Broadcasting desktop canvas to all participants in high resolution</p>
            </div>
          </div>
        ) : (
          /* Video Canvas Grid */
          <div
            style={{
              flex: 1,
              padding: '16px',
              display: 'grid',
              gridTemplateColumns: viewMode === 'speaker' ? '1fr' : 'repeat(auto-fit, minmax(320px, 1fr))',
              gap: '12px',
              alignContent: 'center',
              overflowY: 'auto',
            }}
          >
            {/* 1. Local User Zoom Video Tile */}
            <div
              style={{
                position: 'relative',
                background: '#1f1f23',
                borderRadius: '12px',
                overflow: 'hidden',
                border: audioLevel > 20 ? '2px solid #22c55e' : '2px solid transparent',
                boxShadow: audioLevel > 20 ? '0 0 14px rgba(34, 197, 94, 0.4)' : '0 4px 12px rgba(0,0,0,0.3)',
                aspectRatio: '16 / 9',
                minHeight: '200px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'border 0.15s ease',
              }}
            >
              {camEnabled ? (
                <video
                  ref={localVideoRef}
                  autoPlay
                  playsInline
                  muted
                  style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)' }}
                />
              ) : (
                <div style={{ textAlign: 'center' }}>
                  <div style={{ width: '72px', height: '72px', borderRadius: '50%', background: '#0e72ed', color: '#fff', fontSize: '26px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 8px' }}>
                    {displayName.slice(0, 2).toUpperCase() || 'ME'}
                  </div>
                  <span style={{ fontSize: '12px', color: '#a1a1aa' }}>Camera off</span>
                </div>
              )}

              {/* Lower-left Zoom Name Capsule */}
              <div
                style={{
                  position: 'absolute',
                  bottom: '10px',
                  left: '10px',
                  background: 'rgba(0, 0, 0, 0.75)',
                  backdropFilter: 'blur(4px)',
                  padding: '3px 8px',
                  borderRadius: '6px',
                  fontSize: '11px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>{micEnabled ? (audioLevel > 20 ? '🟢' : '🎤') : '🔇'}</span>
                <span>{displayName} (Host, Me)</span>
                {handRaised && <span>✋</span>}
              </div>
            </div>

            {/* 2. Remote Zoom Participant Tiles */}
            {simulatedParticipants.slice(1).map((p) => (
              <div
                key={p.id}
                style={{
                  position: 'relative',
                  background: '#1f1f23',
                  borderRadius: '12px',
                  overflow: 'hidden',
                  border: p.isSpeaking ? '2px solid #22c55e' : '2px solid transparent',
                  boxShadow: p.isSpeaking ? '0 0 14px rgba(34, 197, 94, 0.4)' : '0 4px 12px rgba(0,0,0,0.3)',
                  aspectRatio: '16 / 9',
                  minHeight: '200px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'border 0.15s ease',
                }}
              >
                {p.hasVideo ? (
                  <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#18181b' }}>
                    <div style={{ width: '72px', height: '72px', borderRadius: '50%', background: p.avatarColor, color: '#fff', fontSize: '26px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {p.name.slice(0, 2).toUpperCase()}
                    </div>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ width: '72px', height: '72px', borderRadius: '50%', background: '#27272a', color: '#d4d4d8', fontSize: '26px', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 8px' }}>
                      {p.name.slice(0, 2).toUpperCase()}
                    </div>
                    <span style={{ fontSize: '12px', color: '#71717a' }}>Camera off</span>
                  </div>
                )}

                {/* Lower-left Name Capsule */}
                <div
                  style={{
                    position: 'absolute',
                    bottom: '10px',
                    left: '10px',
                    background: 'rgba(0, 0, 0, 0.75)',
                    backdropFilter: 'blur(4px)',
                    padding: '3px 8px',
                    borderRadius: '6px',
                    fontSize: '11px',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <span>{p.isMuted ? '🔇' : (p.isSpeaking ? '🟢' : '🎤')}</span>
                  <span>{p.name}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ================= ZOOM RIGHT COLLAPSIBLE DRAWER ================= */}
        {activeDrawer !== 'none' && (
          <div
            style={{
              width: '360px',
              background: '#1c1c20',
              borderLeft: '1px solid #27272a',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '-8px 0 24px rgba(0,0,0,0.4)',
            }}
          >
            {/* Drawer Tab Headers */}
            <div
              style={{
                height: '48px',
                borderBottom: '1px solid #27272a',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0 12px',
                background: '#18181b',
              }}
            >
              <div style={{ display: 'flex', gap: '4px' }}>
                <button
                  type="button"
                  onClick={() => setActiveDrawer('participants')}
                  style={{
                    background: activeDrawer === 'participants' ? '#27272a' : 'transparent',
                    border: 'none',
                    color: activeDrawer === 'participants' ? '#fff' : '#a1a1aa',
                    padding: '6px 10px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  👥 Participants ({simulatedParticipants.length})
                </button>
                <button
                  type="button"
                  onClick={() => setActiveDrawer('chat')}
                  style={{
                    background: activeDrawer === 'chat' ? '#27272a' : 'transparent',
                    border: 'none',
                    color: activeDrawer === 'chat' ? '#fff' : '#a1a1aa',
                    padding: '6px 10px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  💬 Chat
                </button>
                <button
                  type="button"
                  onClick={() => setActiveDrawer('action_items')}
                  style={{
                    background: activeDrawer === 'action_items' ? '#27272a' : 'transparent',
                    border: 'none',
                    color: activeDrawer === 'action_items' ? '#fff' : '#a1a1aa',
                    padding: '6px 10px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  ⚡ AI Notes ({liveActionItems.length})
                </button>
              </div>

              <button
                type="button"
                onClick={() => setActiveDrawer('none')}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#a1a1aa',
                  fontSize: '16px',
                  cursor: 'pointer',
                  padding: '4px',
                }}
              >
                ✕
              </button>
            </div>

            {/* TAB 1: PARTICIPANTS LIST */}
            {activeDrawer === 'participants' && (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '16px' }}>
                <div style={{ fontSize: '12px', fontWeight: 700, color: '#a1a1aa', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  In the Meeting ({simulatedParticipants.length})
                </div>
                <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {simulatedParticipants.map((p) => (
                    <div
                      key={p.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '8px 10px',
                        background: '#242429',
                        borderRadius: '8px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '28px', height: '28px', borderRadius: '50%', background: p.avatarColor, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 700, color: '#fff' }}>
                          {p.name.slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <div style={{ fontSize: '13px', fontWeight: 600, color: '#e4e4e7' }}>
                            {p.name} {p.id === 'p1' && '(Me)'}
                          </div>
                          <span style={{ fontSize: '10px', color: '#a1a1aa' }}>
                            {p.id === 'p1' ? 'Host' : 'Participant'}
                          </span>
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#9ca3af', fontSize: '14px' }}>
                        <span>{p.id === 'p1' ? (micEnabled ? '🎤' : '🔇') : (p.isMuted ? '🔇' : '🎤')}</span>
                        <span>{p.id === 'p1' ? (camEnabled ? '📹' : '🚫') : (p.hasVideo ? '📹' : '🚫')}</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div style={{ paddingTop: '16px', borderTop: '1px solid #27272a', display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={handleCopyInviteLink}
                    style={{
                      flex: 1,
                      background: '#27272a',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '6px',
                      padding: '8px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {copySuccessNotice ? '✓ Copied!' : '🔗 Invite Link'}
                  </button>
                  {isHost && (
                    <button
                      type="button"
                      onClick={() => alert('All participants muted')}
                      style={{
                        flex: 1,
                        background: '#3f3f46',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '6px',
                        padding: '8px',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Mute All
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* TAB 2: CHAT */}
            {activeDrawer === 'chat' && (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <div style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {chatMessages.map((msg, i) => (
                    <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#a1a1aa' }}>
                        <strong style={{ color: msg.isSelf ? '#38bdf8' : '#e4e4e7' }}>{msg.sender}</strong>
                        <span>to {msg.recipient || 'Everyone'}</span>
                        <span style={{ fontSize: '10px', opacity: 0.7 }}>{msg.time}</span>
                      </div>
                      <div
                        style={{
                          background: msg.isSelf ? '#0e72ed' : '#27272a',
                          color: '#fff',
                          padding: '8px 12px',
                          borderRadius: '8px',
                          fontSize: '13px',
                          lineHeight: '1.4',
                          maxWidth: '90%',
                          alignSelf: msg.isSelf ? 'flex-end' : 'flex-start',
                        }}
                      >
                        {msg.text}
                      </div>
                    </div>
                  ))}
                </div>

                <form onSubmit={handleSendChat} style={{ padding: '12px', borderTop: '1px solid #27272a', background: '#18181b' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px', fontSize: '11px', color: '#a1a1aa' }}>
                    <span>To:</span>
                    <select
                      value={chatRecipient}
                      onChange={(e) => setChatRecipient(e.target.value)}
                      style={{ background: '#27272a', color: '#fff', border: 'none', borderRadius: '4px', padding: '2px 6px', fontSize: '11px' }}
                    >
                      <option value="Everyone">Everyone</option>
                      <option value="Sarah Kim">Sarah Kim</option>
                      <option value="Marcus Lee">Marcus Lee</option>
                      <option value="Alex Lin">Alex Lin</option>
                    </select>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                      type="text"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      placeholder="Type message here..."
                      style={{
                        flex: 1,
                        background: '#27272a',
                        border: '1px solid #3f3f46',
                        borderRadius: '6px',
                        padding: '8px 12px',
                        color: '#fff',
                        fontSize: '12px',
                      }}
                    />
                    <button
                      type="submit"
                      style={{
                        background: '#0e72ed',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '6px',
                        padding: '8px 14px',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Send
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* TAB 3: AI NOTES & ACTION ITEMS */}
            {activeDrawer === 'action_items' && (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '16px', overflowY: 'auto' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: '#a1a1aa', textTransform: 'uppercase' }}>
                    Live AI Action Items
                  </div>
                  <span style={{ background: '#f59e0b', color: '#000', fontSize: '10px', fontWeight: 800, padding: '2px 6px', borderRadius: '4px' }}>
                    AUTO-DETECTED
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                  {liveActionItems.length === 0 ? (
                    <div style={{ textAlign: 'center', color: '#71717a', fontSize: '12px', padding: '20px 0' }}>
                      Speak naturally during the meeting. Meetora AI will extract action items and deadlines in real-time.
                    </div>
                  ) : (
                    liveActionItems.map((item, idx) => (
                      <div
                        key={idx}
                        style={{
                          background: '#242429',
                          border: '1px solid #37373f',
                          borderRadius: '8px',
                          padding: '10px 12px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '4px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                          <input type="checkbox" style={{ marginTop: '3px', accentColor: '#22c55e' }} />
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f4f4f5' }}>{item.title}</span>
                        </div>
                        <div style={{ display: 'flex', gap: '8px', fontSize: '11px', color: '#a1a1aa', marginLeft: '22px' }}>
                          <span>👤 {item.assignee || 'Unassigned'}</span>
                          {item.deadline && <span>📅 {item.deadline}</span>}
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* Add Manual Item */}
                <div style={{ borderTop: '1px solid #27272a', paddingTop: '12px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: '#a1a1aa', display: 'block', marginBottom: '6px' }}>
                    Add Task
                  </span>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <input
                      type="text"
                      value={newActionItemTitle}
                      onChange={(e) => setNewActionItemTitle(e.target.value)}
                      placeholder="e.g. Update client slide deck"
                      style={{ flex: 1, background: '#27272a', border: '1px solid #3f3f46', borderRadius: '6px', padding: '6px 10px', color: '#fff', fontSize: '12px' }}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        if (!newActionItemTitle.trim()) return
                        setLiveActionItems((prev) => [
                          ...prev,
                          { id: Date.now(), title: newActionItemTitle.trim(), status: 'pending' }
                        ])
                        setNewActionItemTitle('')
                      }}
                      style={{ background: '#0e72ed', color: '#fff', border: 'none', borderRadius: '6px', padding: '6px 12px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
                    >
                      Add
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ================= REAL ZOOM BOTTOM CONTROL TOOLBAR ================= */}
      <div
        style={{
          height: '76px',
          background: '#18181b',
          borderTop: '1px solid #27272a',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
        }}
      >
        {/* Left: Audio & Video Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* MUTE / UNMUTE */}
          <button
            type="button"
            onClick={() => setMicEnabled((prev) => !prev)}
            style={{
              background: 'transparent',
              border: 'none',
              borderRadius: '8px',
              padding: '6px 12px',
              color: micEnabled ? '#e4e4e7' : '#ef4444',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '4px',
              cursor: 'pointer',
              minWidth: '60px',
            }}
          >
            <span style={{ fontSize: '20px' }}>{micEnabled ? '🎙️' : '🔇'}</span>
            <span style={{ fontSize: '11px', fontWeight: 500 }}>{micEnabled ? 'Mute' : 'Unmute'}</span>
          </button>

          {/* START / STOP VIDEO */}
          <button
            type="button"
            onClick={() => setCamEnabled((prev) => !prev)}
            style={{
              background: 'transparent',
              border: 'none',
              borderRadius: '8px',
              padding: '6px 12px',
              color: camEnabled ? '#e4e4e7' : '#ef4444',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '4px',
              cursor: 'pointer',
              minWidth: '68px',
            }}
          >
            <span style={{ fontSize: '20px' }}>{camEnabled ? '📹' : '🚫'}</span>
            <span style={{ fontSize: '11px', fontWeight: 500 }}>{camEnabled ? 'Stop Video' : 'Start Video'}</span>
          </button>
        </div>

        {/* Center: Main Zoom Controls (Security, Participants, Chat, Share, RECORD, Captions, AI, Reactions) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          {/* Security */}
          <button
            type="button"
            onClick={() => setShowSecurityMenu((prev) => !prev)}
            style={{
              background: showSecurityMenu ? '#27272a' : 'transparent',
              border: 'none',
              borderRadius: '8px',
              padding: '6px 10px',
              color: '#e4e4e7',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '4px',
              cursor: 'pointer',
              minWidth: '64px',
            }}
          >
            <span style={{ fontSize: '20px' }}>🛡️</span>
            <span style={{ fontSize: '11px', fontWeight: 500 }}>Security</span>
          </button>

          {/* Participants */}
          <button
            type="button"
            onClick={() => setActiveDrawer((prev) => (prev === 'participants' ? 'none' : 'participants'))}
            style={{
              background: activeDrawer === 'participants' ? '#27272a' : 'transparent',
              border: 'none',
              borderRadius: '8px',
              padding: '6px 10px',
              color: '#e4e4e7',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '4px',
              cursor: 'pointer',
              minWidth: '72px',
              position: 'relative',
            }}
          >
            <span style={{ fontSize: '20px' }}>👥</span>
            <span style={{ fontSize: '11px', fontWeight: 500 }}>
              Participants <span style={{ color: '#0e72ed' }}>({simulatedParticipants.length})</span>
            </span>
          </button>

          {/* Chat */}
          <button
            type="button"
            onClick={() => setActiveDrawer((prev) => (prev === 'chat' ? 'none' : 'chat'))}
            style={{
              background: activeDrawer === 'chat' ? '#27272a' : 'transparent',
              border: 'none',
              borderRadius: '8px',
              padding: '6px 10px',
              color: '#e4e4e7',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '4px',
              cursor: 'pointer',
              minWidth: '60px',
            }}
          >
            <span style={{ fontSize: '20px' }}>💬</span>
            <span style={{ fontSize: '11px', fontWeight: 500 }}>Chat</span>
          </button>

          {/* ZOOM SHARE SCREEN (PROMINENT GREEN BUTTON) */}
          <button
            type="button"
            onClick={handleToggleScreenShare}
            style={{
              background: screenSharing ? '#ef4444' : '#22c55e',
              border: 'none',
              borderRadius: '8px',
              padding: '6px 14px',
              color: screenSharing ? '#fff' : '#000',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '4px',
              cursor: 'pointer',
              minWidth: '80px',
              boxShadow: '0 2px 10px rgba(34, 197, 94, 0.3)',
            }}
          >
            <span style={{ fontSize: '20px' }}>🖥️</span>
            <span style={{ fontSize: '11px', fontWeight: 700 }}>
              {screenSharing ? 'Stop Share' : 'Share Screen'}
            </span>
          </button>

          {/* ========================================================= */}
          {/* ZOOM RECORD BUTTON (CORE REQUESTED RECORDING OPTION)      */}
          {/* ========================================================= */}
          <button
            type="button"
            onClick={isRecording ? handleStopRecording : handleStartRecording}
            disabled={isRecordingLoading}
            style={{
              background: isRecording ? '#dc2626' : '#27272a',
              border: isRecording ? '2px solid #ef4444' : '1px solid #3f3f46',
              borderRadius: '8px',
              padding: '6px 14px',
              color: '#ffffff',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '4px',
              cursor: isRecordingLoading ? 'not-allowed' : 'pointer',
              minWidth: '84px',
              boxShadow: isRecording ? '0 0 16px rgba(239, 68, 68, 0.6)' : 'none',
              transition: 'all 0.2s ease',
            }}
            title={isRecording ? 'Click to Stop Recording' : 'Click to Record this Meeting (R)'}
          >
            <span style={{ fontSize: '20px', lineHeight: 1 }}>
              {isRecording ? '⏹️' : '🔴'}
            </span>
            <span style={{ fontSize: '11px', fontWeight: 700 }}>
              {isRecordingLoading ? 'Working...' : isRecording ? `Stop REC (${formatTimer(recordingDurationSec)})` : 'Record'}
            </span>
          </button>

          {/* Captions (CC) */}
          <button
            type="button"
            onClick={() => {
              if (!captionConsentGiven) {
                setShowCaptionConsentModal(true)
              } else {
                setCaptionsEnabled((prev) => !prev)
              }
            }}
            style={{
              background: captionsEnabled ? 'rgba(14, 114, 237, 0.25)' : 'transparent',
              border: 'none',
              borderRadius: '8px',
              padding: '6px 10px',
              color: captionsEnabled ? '#38bdf8' : '#e4e4e7',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '4px',
              cursor: 'pointer',
              minWidth: '64px',
            }}
          >
            <span style={{ fontSize: '20px' }}>🗨️</span>
            <span style={{ fontSize: '11px', fontWeight: 500 }}>Captions</span>
          </button>

          {/* AI Notes */}
          <button
            type="button"
            onClick={() => setActiveDrawer((prev) => (prev === 'action_items' ? 'none' : 'action_items'))}
            style={{
              background: activeDrawer === 'action_items' ? '#27272a' : 'transparent',
              border: 'none',
              borderRadius: '8px',
              padding: '6px 10px',
              color: '#e4e4e7',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '4px',
              cursor: 'pointer',
              minWidth: '68px',
            }}
          >
            <span style={{ fontSize: '20px' }}>⚡</span>
            <span style={{ fontSize: '11px', fontWeight: 500 }}>AI Notes</span>
          </button>

          {/* Reactions */}
          <button
            type="button"
            onClick={() => setShowReactionsMenu((prev) => !prev)}
            style={{
              background: showReactionsMenu ? '#27272a' : 'transparent',
              border: 'none',
              borderRadius: '8px',
              padding: '6px 10px',
              color: '#e4e4e7',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '4px',
              cursor: 'pointer',
              minWidth: '64px',
            }}
          >
            <span style={{ fontSize: '20px' }}>😊</span>
            <span style={{ fontSize: '11px', fontWeight: 500 }}>Reactions</span>
          </button>
        </div>

        {/* Right: End / Leave Button (Deep Red Zoom Button) */}
        <div>
          <button
            type="button"
            onClick={() => setShowEndModal(true)}
            style={{
              background: '#dc2626',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              padding: '8px 20px',
              fontSize: '13px',
              fontWeight: 700,
              cursor: 'pointer',
              boxShadow: '0 2px 10px rgba(220, 38, 38, 0.3)',
            }}
          >
            {isHost ? 'End' : 'Leave'}
          </button>
        </div>
      </div>

      {/* ================= ZOOM POPUPS & MODALS ================= */}

      {/* 1. Reactions Popover */}
      {showReactionsMenu && (
        <div
          style={{
            position: 'fixed',
            bottom: '84px',
            left: '50%',
            transform: 'translateX(80px)',
            background: '#1f1f23',
            border: '1px solid #3f3f46',
            borderRadius: '24px',
            padding: '8px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
            zIndex: 100000,
          }}
        >
          {['👏', '👍', '❤️', '😂', '😮', '🎉'].map((emoji) => (
            <button
              key={emoji}
              type="button"
              onClick={() => handleTriggerReaction(emoji)}
              style={{
                background: 'transparent',
                border: 'none',
                fontSize: '22px',
                cursor: 'pointer',
                padding: '4px',
                transition: 'transform 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.2)')}
              onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
            >
              {emoji}
            </button>
          ))}
          <div style={{ width: '1px', height: '24px', background: '#3f3f46', margin: '0 4px' }} />
          <button
            type="button"
            onClick={() => {
              setHandRaised((prev) => !prev)
              setShowReactionsMenu(false)
            }}
            style={{
              background: handRaised ? '#eab308' : '#27272a',
              color: handRaised ? '#000' : '#fff',
              border: 'none',
              borderRadius: '16px',
              padding: '4px 10px',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            {handRaised ? '✋ Lower Hand' : '✋ Raise Hand'}
          </button>
        </div>
      )}

      {/* 2. Zoom Security Menu */}
      {showSecurityMenu && (
        <div
          style={{
            position: 'fixed',
            bottom: '84px',
            left: '50%',
            transform: 'translateX(-190px)',
            background: '#1f1f23',
            border: '1px solid #3f3f46',
            borderRadius: '12px',
            padding: '12px',
            width: '260px',
            boxShadow: '0 10px 30px rgba(0,0,0,0.6)',
            zIndex: 100000,
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            fontSize: '12px',
          }}
        >
          <div style={{ fontWeight: 700, color: '#a1a1aa', borderBottom: '1px solid #27272a', paddingBottom: '6px' }}>
            Security Settings
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={meetingLocked}
              onChange={(e) => setMeetingLocked(e.target.checked)}
              style={{ accentColor: '#0e72ed' }}
            />
            <span>Lock Meeting</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input type="checkbox" defaultChecked style={{ accentColor: '#0e72ed' }} />
            <span>Enable Waiting Room</span>
          </label>
          <div style={{ borderTop: '1px solid #27272a', margin: '4px 0', paddingTop: '4px', fontWeight: 600, color: '#71717a' }}>
            Allow Participants to:
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input type="checkbox" defaultChecked style={{ accentColor: '#0e72ed' }} />
            <span>Share Screen</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input type="checkbox" defaultChecked style={{ accentColor: '#0e72ed' }} />
            <span>Chat with Everyone</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input type="checkbox" defaultChecked style={{ accentColor: '#0e72ed' }} />
            <span>Unmute Themselves</span>
          </label>
        </div>
      )}

      {/* 3. Zoom Meeting Information Dialog (Shield Click) */}
      {showMeetingInfoModal && (
        <div
          style={{
            position: 'fixed',
            top: '56px',
            left: '16px',
            background: '#1f1f23',
            border: '1px solid #3f3f46',
            borderRadius: '12px',
            padding: '20px',
            width: '320px',
            boxShadow: '0 12px 36px rgba(0,0,0,0.6)',
            zIndex: 100000,
            color: '#fff',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '18px', color: '#22c55e' }}>🛡️</span>
              <span style={{ fontWeight: 700, fontSize: '14px' }}>Meeting Information</span>
            </div>
            <button
              type="button"
              onClick={() => setShowMeetingInfoModal(false)}
              style={{ background: 'transparent', border: 'none', color: '#a1a1aa', cursor: 'pointer' }}
            >
              ✕
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '12px' }}>
            <div>
              <span style={{ color: '#a1a1aa', display: 'block' }}>Meeting Topic</span>
              <span style={{ fontWeight: 600 }}>{roomName || meetingStatus?.title || `Weekly meet #${meetingId}`}</span>
            </div>
            <div>
              <span style={{ color: '#a1a1aa', display: 'block' }}>Meeting ID</span>
              <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{meetingStatus?.meeting_code || `${meetingId.toString().padStart(3, '0')} 894 120`}</span>
            </div>
            <div>
              <span style={{ color: '#a1a1aa', display: 'block' }}>Host</span>
              <span>{isHost ? displayName : 'Jordan Davis'}</span>
            </div>
            <div>
              <span style={{ color: '#a1a1aa', display: 'block' }}>Passcode</span>
              <span style={{ fontFamily: 'monospace' }}>{passcode || meetingStatus?.passcode || '684920'}</span>
            </div>
            <div>
              <span style={{ color: '#a1a1aa', display: 'block' }}>Encryption</span>
              <span style={{ color: '#22c55e', fontWeight: 600 }}>🟢 Enhanced 256-bit AES</span>
            </div>
            <div style={{ marginTop: '8px' }}>
              <button
                type="button"
                onClick={handleCopyInviteLink}
                style={{
                  width: '100%',
                  background: '#0e72ed',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '8px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {copySuccessNotice ? '✓ Copied Invitation Link!' : 'Copy Invitation Link'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. Zoom End / Leave Modal */}
      {showEndModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.7)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100001,
          }}
        >
          <div
            style={{
              background: '#1f1f23',
              border: '1px solid #3f3f46',
              borderRadius: '16px',
              padding: '24px',
              maxWidth: '380px',
              width: '100%',
              textAlign: 'center',
              boxShadow: '0 20px 50px rgba(0,0,0,0.6)',
            }}
          >
            <h3 style={{ margin: '0 0 10px', fontSize: '18px', fontWeight: 700, color: '#fff' }}>
              {isHost ? 'End Meeting for All?' : 'Leave Meeting?'}
            </h3>
            <p style={{ margin: '0 0 20px', fontSize: '13px', color: '#a1a1aa', lineHeight: 1.5 }}>
              {isHost
                ? 'You can choose to end the meeting for all attendees or leave the meeting while allowing attendees to stay.'
                : 'Are you sure you want to leave this meeting?'}
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {isHost && (
                <button
                  type="button"
                  onClick={handleEndMeeting}
                  style={{
                    background: '#dc2626',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '10px',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  End Meeting for All
                </button>
              )}
              <button
                type="button"
                onClick={handleSafeLeave}
                style={{
                  background: isHost ? '#374151' : '#dc2626',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '10px',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Leave Meeting
              </button>
              <button
                type="button"
                onClick={() => setShowEndModal(false)}
                style={{
                  background: 'transparent',
                  color: '#a1a1aa',
                  border: 'none',
                  padding: '6px',
                  fontSize: '12px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4b. Ending / Leaving Transition Overlay */}
      {isEndingMeeting && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.85)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100005,
            color: '#fff',
          }}
        >
          <div
            style={{
              background: '#1f1f23',
              border: '1px solid #3f3f46',
              borderRadius: '16px',
              padding: '32px 36px',
              textAlign: 'center',
              boxShadow: '0 20px 50px rgba(0,0,0,0.7)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '16px',
              maxWidth: '380px',
              width: '90%',
            }}
          >
            <div
              style={{
                width: '42px',
                height: '42px',
                border: '4px solid #3f3f46',
                borderTop: '4px solid #dc2626',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }}
            />
            <div>
              <div style={{ fontSize: '16px', fontWeight: 700 }}>
                {isHost ? 'Ending Meeting for All...' : 'Leaving Meeting...'}
              </div>
              <div style={{ fontSize: '13px', color: '#a1a1aa', marginTop: '6px', lineHeight: 1.4 }}>
                Stopping media devices, saving recording, and preparing AI analysis...
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 5. Recording Upload Progress Toast */}
      {uploadProgressMsg && (
        <div
          style={{
            position: 'fixed',
            bottom: '90px',
            left: '50%',
            transform: 'translateX(-50%)',
            background: '#18181b',
            color: '#fff',
            padding: '10px 20px',
            borderRadius: '12px',
            border: '1px solid #0e72ed',
            zIndex: 100000,
            fontWeight: 600,
            fontSize: '13px',
            boxShadow: '0 10px 30px rgba(0,0,0,0.6)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <span>⏳ {uploadProgressMsg}</span>
          {localRecordingUrl && (
            <a
              href={localRecordingUrl}
              download={`zoom_recording_${meetingId}.webm`}
              style={{
                background: '#059669',
                color: '#fff',
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 700,
                textDecoration: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              ⬇️ Download Copy
            </a>
          )}
        </div>
      )}

      {/* 6. Live Caption Consent Modal */}
      {showCaptionConsentModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            zIndex: 100002,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
        >
          <div
            style={{
              background: '#1f1f23',
              border: '1px solid #3f3f46',
              borderRadius: '16px',
              maxWidth: '460px',
              width: '100%',
              padding: '24px',
              color: '#fff',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <span style={{ fontSize: '24px' }}>💬</span>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>Enable Live Captions</h3>
            </div>
            <p style={{ fontSize: '13px', color: '#d4d4d8', lineHeight: 1.6, margin: '0 0 16px' }}>
              Zoom speech recognition engine automatically transcribes spoken audio in real-time.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                type="button"
                onClick={() => setShowCaptionConsentModal(false)}
                style={{ background: 'transparent', border: '1px solid #4b5563', color: '#d1d5db', borderRadius: '8px', padding: '8px 16px', fontSize: '13px', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  if (typeof window !== 'undefined') {
                    localStorage.setItem('meetora_caption_consent', 'true')
                  }
                  setCaptionConsentGiven(true)
                  setCaptionsEnabled(true)
                  setShowCaptionConsentModal(false)
                }}
                style={{ background: '#0e72ed', border: 'none', color: '#fff', borderRadius: '8px', padding: '8px 18px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}
              >
                I Agree & Enable
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )

  // When LiveKit media server is active, wrap with LiveKitRoom so real WebRTC peer audio works
  if (!isSimulatedMode && liveUrl && liveToken) {
    return (
      <LiveKitRoom
        serverUrl={liveUrl}
        token={liveToken}
        connect={true}
        video={camEnabled}
        audio={micEnabled}
        onDisconnected={() => {
          console.warn('[LiveKit Disconnected] Connection closed.')
          if (!isIntentionalLeaveRef.current) {
            setRoomError('LiveKit media server disconnected unexpectedly.')
          } else {
            onLeave()
          }
        }}
        onError={(err) => {
          console.error('[LiveKit Error]', err)
          setRoomError(`LiveKit Connection Error: ${err?.message || String(err)}`)
        }}
        data-lk-theme="default"
        style={{ width: '100%', height: '100%' }}
      >
        <RoomAudioRenderer />
        {zoomMeetingContent}
      </LiveKitRoom>
    )
  }

  // Otherwise render the full Zoom meeting app directly in practice/preview mode
  return zoomMeetingContent
}
