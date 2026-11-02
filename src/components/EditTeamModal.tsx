import React, { useState, useEffect, useRef } from 'react'
import { TeamData } from '../api'

interface EditTeamModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (payload: { name: string; color: string; description?: string }) => Promise<void>
  team: TeamData | null
  theme: 'light' | 'dark'
}

const COLOR_OPTIONS = [
  { id: 'violet', label: 'Violet', bg: 'bg-violet-500', ring: 'ring-violet-400' },
  { id: 'indigo', label: 'Indigo', bg: 'bg-indigo-500', ring: 'ring-indigo-400' },
  { id: 'blue', label: 'Blue', bg: 'bg-blue-500', ring: 'ring-blue-400' },
  { id: 'cyan', label: 'Cyan', bg: 'bg-cyan-500', ring: 'ring-cyan-400' },
  { id: 'emerald', label: 'Emerald', bg: 'bg-emerald-500', ring: 'ring-emerald-400' },
  { id: 'amber', label: 'Amber', bg: 'bg-amber-500', ring: 'ring-amber-400' },
  { id: 'rose', label: 'Rose', bg: 'bg-rose-500', ring: 'ring-rose-400' },
  { id: 'pink', label: 'Pink', bg: 'bg-pink-500', ring: 'ring-pink-400' },
]

export const EditTeamModal: React.FC<EditTeamModalProps> = ({
  isOpen,
  onClose,
  onSave,
  team,
  theme,
}) => {
  const [name, setName] = useState('')
  const [color, setColor] = useState('violet')
  const [description, setDescription] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const modalRef = useRef<HTMLDivElement>(null)
  const nameInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isOpen && team) {
      setName(team.name || '')
      setColor(team.color || 'violet')
      setDescription(team.description || '')
      setErrorMessage(null)
      setIsSaving(false)
      setTimeout(() => nameInputRef.current?.focus(), 50)
    }
  }, [isOpen, team])

  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (!isSaving) onClose()
        return
      }

      if (e.key === 'Tab') {
        const focusables = modalRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), textarea:not([disabled])'
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
  }, [isOpen, isSaving, onClose])

  if (!isOpen || !team) return null

  const isDark = theme === 'dark'
  const isChanged =
    name.trim() !== (team.name || '') ||
    color !== (team.color || 'violet') ||
    description.trim() !== (team.description || '')

  const isNameValid = name.trim().length >= 1 && name.trim().length <= 60

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isNameValid || !isChanged || isSaving) return

    setIsSaving(true)
    setErrorMessage(null)
    try {
      await onSave({
        name: name.trim(),
        color,
        description: description.trim() || undefined,
      })
      onClose()
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to update team settings'
      setErrorMessage(msg)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-team-title"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
        onClick={() => {
          if (!isSaving) onClose()
        }}
      />

      {/* Modal Dialog */}
      <div
        ref={modalRef}
        className={`relative w-full max-w-lg rounded-2xl border p-6 shadow-2xl transition-all anim-pop ${
          isDark
            ? 'bg-[#13111c] border-white/10 text-white'
            : 'bg-white border-neutral-200 text-neutral-900 shadow-xl'
        }`}
      >
        <div className="flex items-center justify-between pb-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center bg-${color}-500/20 text-${color}-400 border border-${color}-500/30 font-bold text-sm`}>
              {name.trim() ? name.trim().charAt(0).toUpperCase() : 'T'}
            </div>
            <div>
              <h2 id="edit-team-title" className="text-lg font-semibold tracking-tight">
                Edit Team Settings
              </h2>
              <p className={`text-xs ${isDark ? 'text-white/50' : 'text-neutral-500'}`}>
                Update team name, color branding, and workspace description
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isSaving}
            className={`p-1.5 rounded-lg transition-colors ${
              isDark
                ? 'hover:bg-white/10 text-white/60 hover:text-white'
                : 'hover:bg-neutral-100 text-neutral-500 hover:text-neutral-800'
            }`}
            aria-label="Close modal"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {errorMessage && (
          <div className="mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-start gap-2">
            <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          {/* Team Name */}
          <div>
            <label className={`block text-xs font-medium mb-1.5 ${isDark ? 'text-white/80' : 'text-neutral-700'}`}>
              Team Name <span className="text-red-400">*</span>
            </label>
            <input
              ref={nameInputRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={60}
              placeholder="e.g. Acme Product Team"
              className={`w-full px-3.5 py-2.5 rounded-xl text-sm border transition-colors outline-none focus:ring-2 focus:ring-violet-500/50 ${
                isDark
                  ? 'bg-white/5 border-white/10 text-white placeholder-white/30 focus:border-violet-500'
                  : 'bg-neutral-50 border-neutral-300 text-neutral-900 placeholder-neutral-400 focus:border-violet-600'
              } ${!isNameValid && name ? 'border-red-500 focus:border-red-500 focus:ring-red-500/30' : ''}`}
            />
            <div className="flex justify-between items-center mt-1 text-[11px]">
              <span className={!isNameValid && name ? 'text-red-400' : isDark ? 'text-white/40' : 'text-neutral-400'}>
                {name.length === 0 ? 'Name is required' : `${name.length}/60 characters`}
              </span>
            </div>
          </div>

          {/* Color Badge */}
          <div>
            <label className={`block text-xs font-medium mb-2 ${isDark ? 'text-white/80' : 'text-neutral-700'}`}>
              Theme Color Badge
            </label>
            <div className="flex flex-wrap gap-2.5">
              {COLOR_OPTIONS.map((c) => {
                const isSelected = color === c.id
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setColor(c.id)}
                    className={`w-7 h-7 rounded-full ${c.bg} transition-all flex items-center justify-center ${
                      isSelected
                        ? `ring-2 ring-offset-2 ring-offset-[#13111c] ring-white scale-110 shadow-lg`
                        : 'opacity-70 hover:opacity-100 hover:scale-105'
                    }`}
                    title={c.label}
                  >
                    {isSelected && (
                      <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Description */}
          <div>
            <label className={`block text-xs font-medium mb-1.5 ${isDark ? 'text-white/80' : 'text-neutral-700'}`}>
              Description <span className={`text-[10px] ${isDark ? 'text-white/40' : 'text-neutral-400'}`}>(Optional)</span>
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this team focus on?"
              className={`w-full px-3.5 py-2.5 rounded-xl text-sm border transition-colors outline-none resize-none focus:ring-2 focus:ring-violet-500/50 ${
                isDark
                  ? 'bg-white/5 border-white/10 text-white placeholder-white/30 focus:border-violet-500'
                  : 'bg-neutral-50 border-neutral-300 text-neutral-900 placeholder-neutral-400 focus:border-violet-600'
              }`}
            />
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-white/10">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
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
              disabled={!isChanged || !isNameValid || isSaving}
              className={`px-5 py-2 rounded-xl text-sm font-medium text-white transition-all btn-anim flex items-center gap-2 ${
                !isChanged || !isNameValid || isSaving
                  ? 'bg-violet-600/40 cursor-not-allowed opacity-60'
                  : 'bg-violet-600 hover:bg-violet-500 shadow-lg shadow-violet-600/30'
              }`}
            >
              {isSaving && (
                <svg className="w-4 h-4 animate-spin text-white" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
              )}
              {isSaving ? 'Saving Changes...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

