import React, { useState, useEffect, useRef } from 'react'
import { TeamData } from '../api'

interface DeleteTeamModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (meetingsAction: 'move' | 'delete') => Promise<void>
  team: TeamData | null
  theme: 'light' | 'dark'
}

export const DeleteTeamModal: React.FC<DeleteTeamModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  team,
  theme,
}) => {
  const [typedName, setTypedName] = useState('')
  const [meetingsAction, setMeetingsAction] = useState<'move' | 'delete'>('move')
  const [isDeleting, setIsDeleting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const modalRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isOpen) {
      setTypedName('')
      setMeetingsAction('move')
      setIsDeleting(false)
      setErrorMessage(null)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (!isDeleting) onClose()
        return
      }

      if (e.key === 'Tab') {
        const focusables = modalRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled])'
        )
        if (!focusables || focusables.length === 0) return
        const first = focusables[0]
        const last = focusables[focusables.length - 1]

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, isDeleting, onClose])

  if (!isOpen || !team) return null

  const isDark = theme === 'dark'
  const isMatch = typedName.trim() === team.name.trim()

  const handleDelete = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isMatch || isDeleting) return

    setIsDeleting(true)
    setErrorMessage(null)
    try {
      await onConfirm(meetingsAction)
      onClose()
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to delete team'
      setErrorMessage(msg)
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-team-title"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/75 backdrop-blur-sm transition-opacity"
        onClick={() => {
          if (!isDeleting) onClose()
        }}
      />

      {/* Modal Dialog */}
      <div
        ref={modalRef}
        className={`relative w-full max-w-lg rounded-2xl border p-6 shadow-2xl transition-all anim-pop ${
          isDark
            ? 'bg-[#15121e] border-red-500/20 text-white'
            : 'bg-white border-neutral-200 text-neutral-900 shadow-xl'
        }`}
      >
        <div className="flex items-center gap-3 pb-4 border-b border-white/10">
          <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-400 shrink-0">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </div>
          <div>
            <h2 id="delete-team-title" className="text-lg font-semibold tracking-tight text-red-400">
              Delete Team & Workspace
            </h2>
            <p className={`text-xs ${isDark ? 'text-white/50' : 'text-neutral-500'}`}>
              This action permanently destroys this team space and cannot be undone.
            </p>
          </div>
        </div>

        {errorMessage && (
          <div className="mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-start gap-2">
            <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleDelete} className="mt-5 space-y-4">
          {/* Radio choice for meetings */}
          <div>
            <label className={`block text-xs font-semibold mb-2 ${isDark ? 'text-white/80' : 'text-neutral-700'}`}>
              What should happen to the team's meetings?
            </label>
            <div className="space-y-2">
              <label
                className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                  meetingsAction === 'move'
                    ? 'border-violet-500/60 bg-violet-500/10'
                    : isDark
                    ? 'border-white/10 bg-white/5 hover:bg-white/10'
                    : 'border-neutral-200 bg-neutral-50 hover:bg-neutral-100'
                }`}
              >
                <input
                  type="radio"
                  name="meetingsAction"
                  checked={meetingsAction === 'move'}
                  onChange={() => setMeetingsAction('move')}
                  className="mt-1 accent-violet-600"
                />
                <div>
                  <div className="text-sm font-medium">Move to Personal Workspace (Recommended)</div>
                  <div className={`text-xs ${isDark ? 'text-white/60' : 'text-neutral-500'}`}>
                    Preserves all meeting transcripts, summaries, and action items in your personal workspace.
                  </div>
                </div>
              </label>

              <label
                className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                  meetingsAction === 'delete'
                    ? 'border-red-500/60 bg-red-500/10'
                    : isDark
                    ? 'border-white/10 bg-white/5 hover:bg-white/10'
                    : 'border-neutral-200 bg-neutral-50 hover:bg-neutral-100'
                }`}
              >
                <input
                  type="radio"
                  name="meetingsAction"
                  checked={meetingsAction === 'delete'}
                  onChange={() => setMeetingsAction('delete')}
                  className="mt-1 accent-red-600"
                />
                <div>
                  <div className="text-sm font-medium text-red-400">Permanently Delete All Meetings</div>
                  <div className={`text-xs ${isDark ? 'text-white/60' : 'text-neutral-500'}`}>
                    Removes audio files, vector index embeddings, and action items. AI model retraining records are detached and kept.
                  </div>
                </div>
              </label>
            </div>
          </div>

          {/* Typing confirmation */}
          <div className="pt-2">
            <label className={`block text-xs font-medium mb-1.5 ${isDark ? 'text-white/80' : 'text-neutral-700'}`}>
              To confirm, type <span className="font-bold text-red-400 select-all">{team.name}</span> below:
            </label>
            <input
              ref={inputRef}
              type="text"
              value={typedName}
              onChange={(e) => setTypedName(e.target.value)}
              placeholder={team.name}
              className={`w-full px-3.5 py-2.5 rounded-xl text-sm border transition-colors outline-none focus:ring-2 ${
                isDark
                  ? 'bg-white/5 border-white/10 text-white placeholder-white/20 focus:border-red-500 focus:ring-red-500/30'
                  : 'bg-neutral-50 border-neutral-300 text-neutral-900 placeholder-neutral-400 focus:border-red-500 focus:ring-red-500/30'
              }`}
            />
          </div>

          {/* Action buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-white/10">
            <button
              type="button"
              onClick={onClose}
              disabled={isDeleting}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                isDark
                  ? 'bg-white/5 hover:bg-white/10 text-white/80'
                  : 'bg-neutral-100 hover:bg-neutral-200 text-neutral-700'
              }`}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!isMatch || isDeleting}
              className={`px-5 py-2 rounded-xl text-sm font-medium text-white transition-all btn-anim flex items-center gap-2 ${
                !isMatch || isDeleting
                  ? 'bg-red-500/40 cursor-not-allowed opacity-50'
                  : 'bg-red-600 hover:bg-red-500 shadow-lg shadow-red-600/30'
              }`}
            >
              {isDeleting && (
                <svg className="w-4 h-4 animate-spin text-white" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
              )}
              {isDeleting ? 'Deleting Team...' : 'Permanently Delete Team'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

