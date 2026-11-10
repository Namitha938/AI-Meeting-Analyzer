import React, { createContext, useContext, useState, useRef, useEffect, ReactNode } from 'react'

export type RecordingSource = 'recorder_modal' | 'live_room' | null

export interface ActiveRecordingSession {
  source: RecordingSource
  meetingId?: number | string
  title?: string
  stopAndUpload: () => Promise<void>
  stopMediaTracks: () => void
}

export interface RecordingContextType {
  isRecording: boolean
  source: RecordingSource
  elapsedSeconds: number
  activeSession: ActiveRecordingSession | null
  startRecordingSession: (session: ActiveRecordingSession) => void
  stopRecordingSession: () => Promise<void>
  setElapsedSeconds: React.Dispatch<React.SetStateAction<number>>
}

const RecordingContext = createContext<RecordingContextType | undefined>(undefined)

export const RecordingProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isRecording, setIsRecording] = useState<boolean>(false)
  const [source, setSource] = useState<RecordingSource>(null)
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0)
  const [activeSession, setActiveSession] = useState<ActiveRecordingSession | null>(null)
  const timerRef = useRef<any>(null)

  useEffect(() => {
    if (isRecording) {
      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1)
      }, 1000)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
      setElapsedSeconds(0)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [isRecording])

  // Prevent silent loss on browser tab close or reload
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isRecording) {
        e.preventDefault()
        e.returnValue = 'A recording is currently in progress. If you leave, the recording may be interrupted or lost.'
      }
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [isRecording])

  const startRecordingSession = (session: ActiveRecordingSession) => {
    setActiveSession(session)
    setSource(session.source)
    setElapsedSeconds(0)
    setIsRecording(true)
  }

  const stopRecordingSession = async () => {
    if (!isRecording && !activeSession) return
    setIsRecording(false)
    const session = activeSession
    setActiveSession(null)
    setSource(null)

    if (session) {
      try {
        await session.stopAndUpload()
      } catch (err) {
        console.error('Failed to stop and upload recording:', err)
      } finally {
        try {
          session.stopMediaTracks()
        } catch (e) {
          console.warn('Failed to stop media tracks:', e)
        }
      }
    }
  }

  return (
    <RecordingContext.Provider
      value={{
        isRecording,
        source,
        elapsedSeconds,
        activeSession,
        startRecordingSession,
        stopRecordingSession,
        setElapsedSeconds,
      }}
    >
      {children}
    </RecordingContext.Provider>
  )
}

export const useRecording = (): RecordingContextType => {
  const context = useContext(RecordingContext)
  if (!context) {
    throw new Error('useRecording must be used within a RecordingProvider')
  }
  return context
}

