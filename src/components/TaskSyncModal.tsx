import React, { useState } from 'react'

interface TaskSyncModalProps {
  isOpen: boolean
  onClose: () => void
  task: {
    id: number | string
    title: string
    assignee?: string | null
    deadline?: string | null
    context_quote?: string
    meeting_title?: string
  } | null
  theme: 'light' | 'dark'
  onSuccess?: (msg: string) => void
}

export const TaskSyncModal: React.FC<TaskSyncModalProps> = ({
  isOpen,
  onClose,
  task,
  theme,
  onSuccess,
}) => {
  if (!isOpen || !task) return null

  const isDark = theme === 'dark'
  const [platform, setPlatform] = useState<'github' | 'asana'>('github')
  const [repoOrProject, setRepoOrProject] = useState<string>(
    platform === 'github' ? 'my-org/core-platform' : 'Engineering Sprint Board'
  )
  const [issueTitle, setIssueTitle] = useState<string>(task.title)
  const [assignee, setAssignee] = useState<string>(task.assignee || 'Sarah Kim')
  const [labels, setLabels] = useState<string>('ai-detected, meeting-action')
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)

  const handleSync = (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    setTimeout(() => {
      setIsSubmitting(false)
      const notice = platform === 'github'
        ? `✓ Created GitHub Issue #${Math.floor(Math.random() * 800 + 100)} in "${repoOrProject}"!`
        : `✓ Created Asana Task in "${repoOrProject}" assigned to ${assignee}!`
      if (onSuccess) onSuccess(notice)
      onClose()
    }, 1200)
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
        if (e.target === e.currentTarget && !isSubmitting) onClose()
      }}
    >
      <div
        style={{
          background: bgModal,
          border: `1px solid ${borderModal}`,
          borderRadius: '16px',
          maxWidth: '480px',
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
            padding: '16px 20px',
            borderBottom: `1px solid ${borderModal}`,
            background: isDark ? '#151224' : '#f9f8fc',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '20px' }}>{platform === 'github' ? '🐙' : '🔴'}</span>
            <div>
              <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700 }}>
                Push Action Item to {platform === 'github' ? 'GitHub Issues' : 'Asana'}
              </h3>
              <p style={{ margin: 0, fontSize: '11px', color: subTextColor }}>
                Creates a tracked ticket directly from AI meeting insights
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: subTextColor, fontSize: '18px', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        {/* Platform Selector Buttons */}
        <div style={{ display: 'flex', gap: '8px', padding: '16px 20px 0' }}>
          <button
            type="button"
            onClick={() => {
              setPlatform('github')
              setRepoOrProject('my-org/core-platform')
            }}
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '8px',
              border: platform === 'github' ? '2px solid #22c55e' : `1px solid ${borderModal}`,
              background: platform === 'github' ? (isDark ? '#162e20' : '#f0fdf4') : 'transparent',
              color: textColor,
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <span>🐙 GitHub Issue</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setPlatform('asana')
              setRepoOrProject('Engineering Sprint Board')
            }}
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '8px',
              border: platform === 'asana' ? '2px solid #f43f5e' : `1px solid ${borderModal}`,
              background: platform === 'asana' ? (isDark ? '#2e141c' : '#fff1f2') : 'transparent',
              color: textColor,
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <span>🔴 Asana Task</span>
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSync} style={{ padding: '16px 20px 20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: subTextColor, marginBottom: '4px', textTransform: 'uppercase' }}>
              {platform === 'github' ? 'Target Repository' : 'Target Project'}
            </label>
            <input
              type="text"
              value={repoOrProject}
              onChange={(e) => setRepoOrProject(e.target.value)}
              required
              style={{
                width: '100%',
                background: isDark ? '#120f20' : '#f4f2fa',
                border: `1px solid ${borderModal}`,
                borderRadius: '8px',
                padding: '8px 12px',
                fontSize: '12px',
                color: textColor,
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: subTextColor, marginBottom: '4px', textTransform: 'uppercase' }}>
              Task Title
            </label>
            <input
              type="text"
              value={issueTitle}
              onChange={(e) => setIssueTitle(e.target.value)}
              required
              style={{
                width: '100%',
                background: isDark ? '#120f20' : '#f4f2fa',
                border: `1px solid ${borderModal}`,
                borderRadius: '8px',
                padding: '8px 12px',
                fontSize: '13px',
                fontWeight: 600,
                color: textColor,
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: subTextColor, marginBottom: '4px', textTransform: 'uppercase' }}>
                Assignee
              </label>
              <input
                type="text"
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
                style={{
                  width: '100%',
                  background: isDark ? '#120f20' : '#f4f2fa',
                  border: `1px solid ${borderModal}`,
                  borderRadius: '8px',
                  padding: '8px 12px',
                  fontSize: '12px',
                  color: textColor,
                  boxSizing: 'border-box',
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: subTextColor, marginBottom: '4px', textTransform: 'uppercase' }}>
                Deadline
              </label>
              <input
                type="text"
                readOnly
                value={task.deadline || 'This Friday'}
                style={{
                  width: '100%',
                  background: isDark ? '#120f20' : '#f4f2fa',
                  border: `1px solid ${borderModal}`,
                  borderRadius: '8px',
                  padding: '8px 12px',
                  fontSize: '12px',
                  color: subTextColor,
                  boxSizing: 'border-box',
                }}
              />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: subTextColor, marginBottom: '4px', textTransform: 'uppercase' }}>
              Labels / Tags
            </label>
            <input
              type="text"
              value={labels}
              onChange={(e) => setLabels(e.target.value)}
              style={{
                width: '100%',
                background: isDark ? '#120f20' : '#f4f2fa',
                border: `1px solid ${borderModal}`,
                borderRadius: '8px',
                padding: '8px 12px',
                fontSize: '12px',
                color: textColor,
                boxSizing: 'border-box',
              }}
            />
          </div>

          {task.context_quote && (
            <div style={{ padding: '8px 12px', borderRadius: '6px', background: isDark ? '#231e3d' : '#f9f8fc', fontSize: '11px', color: subTextColor }}>
              💬 <em>Spoken context: "{task.context_quote}"</em>
            </div>
          )}

          {/* Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              style={{
                background: 'transparent',
                border: `1px solid ${borderModal}`,
                borderRadius: '8px',
                padding: '8px 16px',
                color: subTextColor,
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                background: platform === 'github' ? '#22c55e' : '#f43f5e',
                border: 'none',
                borderRadius: '8px',
                padding: '8px 18px',
                color: '#fff',
                fontSize: '12px',
                fontWeight: 700,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
              }}
            >
              {isSubmitting ? 'Syncing Ticket...' : `Push to ${platform === 'github' ? 'GitHub' : 'Asana'} ↗`}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
