import React, { useEffect, useRef, useState } from 'react'

interface EditMeetingModalProps {
  isOpen: boolean
  onClose: () => void
  meeting: any
  onSave: (updates: {
    title: string
    tag: string
    description?: string
    scheduled_at?: string
    updated_at?: string
  }) => Promise<void>
  theme: 'light' | 'dark'
}

const TAG_OPTIONS = ['Product', 'Research', 'Planning', 'Design', 'General']

export const EditMeetingModal: React.FC<EditMeetingModalProps> = ({
  isOpen,
  onClose,
  meeting,
  onSave,
  theme,
}) => {
  const modalRef = useRef<HTMLDivElement>(null)
  const titleInputRef = useRef<HTMLInputElement>(null)

  const [title, setTitle] = useState('')
  const [tag, setTag] = useState('Product')
  const [description, setDescription] = useState('')
  const [scheduledAt, setScheduledAt] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  // Reset/prefill whenever meeting or isOpen changes
  useEffect(() => {
    if (!isOpen || !meeting) return

    const initialTitle = meeting.title || ''
    const initialTag = meeting.tag || (meeting.tags && meeting.tags[0]) || 'Product'
    const initialDesc = meeting.description || ''
    let initialDate = ''
    if (meeting.scheduled_at) {
      try {
        const d = new Date(meeting.scheduled_at)
        initialDate = d.toISOString().slice(0, 16)
      } catch {
        initialDate = ''
      }
    }

    setTitle(initialTitle)
    setTag(TAG_OPTIONS.includes(initialTag) ? initialTag : 'Product')
    setDescription(initialDesc)
    setScheduledAt(initialDate)
    setErrorMsg('')
    setIsSaving(false)

    setTimeout(() => {
      titleInputRef.current?.focus()
    }, 50)
  }, [isOpen, meeting])

  // Check if modified
  const originalTitle = meeting?.title || ''
  const originalTag = meeting?.tag || (meeting?.tags && meeting.tags[0]) || 'Product'
  const originalDesc = meeting?.description || ''
  let originalDate = ''
  if (meeting?.scheduled_at) {
    try {
      originalDate = new Date(meeting.scheduled_at).toISOString().slice(0, 16)
    } catch {
      originalDate = ''
    }
  }

  const hasChanged =
    title.trim() !== originalTitle.trim() ||
    tag !== originalTag ||
    description.trim() !== originalDesc.trim() ||
    scheduledAt !== originalDate

  // Focus trap and Escape key listener
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (!isSaving) onClose()
        return
      }

      if (e.key === 'Tab') {
        const focusableElements = modalRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])'
        )
        if (!focusableElements || focusableElements.length === 0) return

        const first = focusableElements[0]
        const last = focusableElements[focusableElements.length - 1]

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault()
            last.focus()
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault()
            first.focus()
          }
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, isSaving, onClose])

  if (!isOpen || !meeting) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) {
      setErrorMsg('Meeting title is required.')
      return
    }
    if (title.trim().length > 200) {
      setErrorMsg('Meeting title must be 200 characters or less.')
      return
    }

    setErrorMsg('')
    setIsSaving(true)
    try {
      await onSave({
        title: title.trim(),
        tag,
        description: description.trim(),
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : undefined,
        updated_at: meeting.updated_at,
      })
      onClose()
    } catch (err: any) {
      if (err?.response?.status === 409) {
        setErrorMsg('This meeting was changed by someone else. Reload to see the latest version.')
      } else if (err?.response?.status === 403) {
        setErrorMsg('Forbidden: You do not have permission to edit this meeting.')
      } else {
        setErrorMsg(err?.response?.data?.detail || err?.message || 'Failed to update meeting.')
      }
    } finally {
      setIsSaving(false)
    }
  }

  const isDark = theme === 'dark'

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        background: 'rgba(10, 8, 22, 0.75)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSaving) onClose()
      }}
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-meeting-dialog-title"
        className="anim-fade-up"
        style={{
          width: '100%',
          maxWidth: '520px',
          background: isDark ? '#18142a' : '#ffffff',
          color: isDark ? '#f0eeff' : '#1f1b2e',
          borderRadius: '16px',
          boxShadow: '0 25px 60px rgba(0, 0, 0, 0.45)',
          border: `1px solid ${isDark ? '#332959' : '#e5e7eb'}`,
          overflow: 'hidden',
          padding: '26px',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <div>
            <h2
              id="edit-meeting-dialog-title"
              style={{
                fontSize: '18px',
                fontWeight: 700,
                margin: 0,
                color: isDark ? '#fff' : '#111827',
              }}
            >
              Edit Meeting Details
            </h2>
            <small style={{ color: '#888', fontSize: '12px' }}>
              Update title, category tag, scheduled timing, and notes
            </small>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            aria-label="Close dialog"
            style={{
              background: 'transparent',
              border: 'none',
              cursor: isSaving ? 'not-allowed' : 'pointer',
              color: isDark ? '#a5a0c0' : '#6b7280',
              fontSize: '18px',
              fontWeight: 700,
              padding: '4px 8px',
              borderRadius: '6px',
            }}
          >
            ✕
          </button>
        </div>

        {/* Error notice */}
        {errorMsg && (
          <div
            role="alert"
            style={{
              background: isDark ? '#451a03' : '#fef2f2',
              border: `1px solid ${isDark ? '#dc2626' : '#f87171'}`,
              color: isDark ? '#fecaca' : '#991b1b',
              padding: '10px 14px',
              borderRadius: '8px',
              marginBottom: '16px',
              fontSize: '12px',
              lineHeight: 1.4,
            }}
          >
            <b>{errorMsg}</b>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Title Field */}
          <div style={{ marginBottom: '16px' }}>
            <label
              htmlFor="edit-meeting-title-input"
              style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                marginBottom: '6px',
                color: isDark ? '#c4b5fd' : '#4b5563',
              }}
            >
              Meeting Title <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input
              id="edit-meeting-title-input"
              ref={titleInputRef}
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Weekly product sync"
              required
              maxLength={200}
              disabled={isSaving}
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: '8px',
                fontSize: '13px',
                border: `1px solid ${!title.trim() && errorMsg ? '#ef4444' : isDark ? '#372d5b' : '#d1d5db'}`,
                background: isDark ? '#231c3d' : '#f9fafb',
                color: isDark ? '#fff' : '#111827',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Grid row: Tag and Scheduled Date */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '16px' }}>
            <div>
              <label
                htmlFor="edit-meeting-tag-select"
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  marginBottom: '6px',
                  color: isDark ? '#c4b5fd' : '#4b5563',
                }}
              >
                Category Tag
              </label>
              <select
                id="edit-meeting-tag-select"
                value={tag}
                onChange={(e) => setTag(e.target.value)}
                disabled={isSaving}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  fontSize: '13px',
                  border: `1px solid ${isDark ? '#372d5b' : '#d1d5db'}`,
                  background: isDark ? '#231c3d' : '#f9fafb',
                  color: isDark ? '#fff' : '#111827',
                  outline: 'none',
                  boxSizing: 'border-box',
                  cursor: 'pointer',
                }}
              >
                {TAG_OPTIONS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="edit-meeting-date-input"
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  marginBottom: '6px',
                  color: isDark ? '#c4b5fd' : '#4b5563',
                }}
              >
                Scheduled Date/Time
              </label>
              <input
                id="edit-meeting-date-input"
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                disabled={isSaving}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  fontSize: '12px',
                  border: `1px solid ${isDark ? '#372d5b' : '#d1d5db'}`,
                  background: isDark ? '#231c3d' : '#f9fafb',
                  color: isDark ? '#fff' : '#111827',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>
          </div>

          {/* Description / Notes */}
          <div style={{ marginBottom: '22px' }}>
            <label
              htmlFor="edit-meeting-desc-input"
              style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                marginBottom: '6px',
                color: isDark ? '#c4b5fd' : '#4b5563',
              }}
            >
              Description & Agenda Notes
            </label>
            <textarea
              id="edit-meeting-desc-input"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Add key context, objective, or agenda points for this meeting..."
              disabled={isSaving}
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: '8px',
                fontSize: '13px',
                border: `1px solid ${isDark ? '#372d5b' : '#d1d5db'}`,
                background: isDark ? '#231c3d' : '#f9fafb',
                color: isDark ? '#fff' : '#111827',
                outline: 'none',
                boxSizing: 'border-box',
                resize: 'vertical',
                fontFamily: 'inherit',
              }}
            />
          </div>

          {/* Modal Buttons */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="btn-anim"
              style={{
                padding: '9px 18px',
                borderRadius: '8px',
                border: `1px solid ${isDark ? '#372d5b' : '#d1d5db'}`,
                background: 'transparent',
                color: 'inherit',
                cursor: isSaving ? 'not-allowed' : 'pointer',
                fontWeight: 600,
                fontSize: '13px',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!hasChanged || !title.trim() || isSaving}
              className="btn-anim"
              style={{
                padding: '9px 20px',
                borderRadius: '8px',
                background: '#6d55d8',
                color: '#ffffff',
                border: 'none',
                cursor: !hasChanged || !title.trim() || isSaving ? 'not-allowed' : 'pointer',
                fontWeight: 700,
                fontSize: '13px',
                boxShadow: '0 4px 14px rgba(109, 85, 216, 0.35)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                opacity: !hasChanged || !title.trim() || isSaving ? 0.6 : 1,
              }}
            >
              {isSaving ? (
                <>
                  <span
                    style={{
                      width: '12px',
                      height: '12px',
                      border: '2px solid rgba(255,255,255,0.4)',
                      borderTopColor: '#fff',
                      borderRadius: '50%',
                      display: 'inline-block',
                      animation: 'spin 1s linear infinite',
                    }}
                  />
                  Saving...
                </>
              ) : (
                'Save changes'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

