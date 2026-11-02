import React, { useEffect, useRef } from 'react'

interface DeleteMeetingModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void | Promise<void>
  meetingTitle: string
  isBulk?: boolean
  count?: number
  isDeleting: boolean
  theme: 'light' | 'dark'
}

export const DeleteMeetingModal: React.FC<DeleteMeetingModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  meetingTitle,
  isBulk = false,
  count = 1,
  isDeleting,
  theme,
}) => {
  const modalRef = useRef<HTMLDivElement>(null)
  const cancelBtnRef = useRef<HTMLButtonElement>(null)
  const confirmBtnRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!isOpen) return

    // Focus cancel button on open for safety
    setTimeout(() => {
      cancelBtnRef.current?.focus()
    }, 50)

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (!isDeleting) onClose()
        return
      }

      if (e.key === 'Tab') {
        // Focus trapping between Cancel and Delete buttons
        const focusableElements = modalRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled])'
        )
        if (!focusableElements || focusableElements.length === 0) return

        const firstElement = focusableElements[0]
        const lastElement = focusableElements[focusableElements.length - 1]

        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            e.preventDefault()
            lastElement.focus()
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault()
            firstElement.focus()
          }
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, isDeleting, onClose])

  if (!isOpen) return null

  const headline = isBulk
    ? `Delete ${count} selected meetings?`
    : `Delete ${meetingTitle}?`

  const bodyDescription = isBulk
    ? `This permanently removes their transcripts, action items, decisions, and recordings. This cannot be undone.`
    : `This permanently removes its transcript, action items, and recording. This cannot be undone.`

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
        if (e.target === e.currentTarget && !isDeleting) onClose()
      }}
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-meeting-dialog-title"
        aria-describedby="delete-meeting-dialog-desc"
        className="anim-fade-up"
        style={{
          width: '100%',
          maxWidth: '460px',
          background: theme === 'dark' ? '#18142a' : '#ffffff',
          color: theme === 'dark' ? '#f0eeff' : '#1f1b2e',
          borderRadius: '16px',
          boxShadow: '0 25px 60px rgba(0, 0, 0, 0.45)',
          border: `1px solid ${theme === 'dark' ? '#332959' : '#e5e7eb'}`,
          overflow: 'hidden',
          padding: '24px',
        }}
      >
        {/* Warning Icon Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '16px' }}>
          <span
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '12px',
              background: '#fee2e2',
              color: '#dc2626',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '20px',
              flexShrink: 0,
            }}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M3 6h18"/>
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
              <line x1="10" y1="11" x2="10" y2="17"/>
              <line x1="14" y1="11" x2="14" y2="17"/>
            </svg>
          </span>
          <div>
            <h2
              id="delete-meeting-dialog-title"
              style={{
                fontSize: '17px',
                fontWeight: 700,
                margin: 0,
                color: theme === 'dark' ? '#fff' : '#111827',
                lineHeight: 1.3,
              }}
            >
              {headline}
            </h2>
            <small style={{ color: '#ef4444', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Permanent Deletion Warning
            </small>
          </div>
        </div>

        {/* Dialog Description */}
        <p
          id="delete-meeting-dialog-desc"
          style={{
            margin: '0 0 24px',
            fontSize: '13px',
            color: theme === 'dark' ? '#c4b5fd' : '#4b5563',
            lineHeight: 1.55,
          }}
        >
          {bodyDescription}
        </p>

        {/* Buttons */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '10px',
          }}
        >
          <button
            ref={cancelBtnRef}
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="btn-anim"
            style={{
              padding: '9px 18px',
              borderRadius: '9px',
              border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
              background: 'transparent',
              color: 'inherit',
              cursor: isDeleting ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: '13px',
            }}
          >
            Cancel
          </button>
          <button
            ref={confirmBtnRef}
            type="button"
            onClick={onConfirm}
            disabled={isDeleting}
            className="btn-anim"
            style={{
              padding: '9px 20px',
              borderRadius: '9px',
              background: '#dc2626',
              color: '#ffffff',
              border: 'none',
              cursor: isDeleting ? 'not-allowed' : 'pointer',
              fontWeight: 700,
              fontSize: '13px',
              boxShadow: '0 4px 14px rgba(220, 38, 38, 0.35)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              opacity: isDeleting ? 0.75 : 1,
            }}
          >
            {isDeleting ? (
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
                Deleting...
              </>
            ) : (
              'Delete'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

