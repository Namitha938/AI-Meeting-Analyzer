import React, { useState, useEffect } from 'react'
import { complianceService, AuditLogItem } from '../api'

interface ComplianceAuditVaultProps {
  theme: 'light' | 'dark'
}

export const ComplianceAuditVault: React.FC<ComplianceAuditVaultProps> = ({ theme }) => {
  const [logs, setLogs] = useState<AuditLogItem[]>([])
  const [loading, setLoading] = useState(true)
  const [severityFilter, setSeverityFilter] = useState<string>('all')
  const [exporting, setExporting] = useState<string | null>(null)
  const [showGdprModal, setShowGdprModal] = useState(false)
  const [purgeEmail, setPurgeEmail] = useState('')
  const [purgeNotice, setPurgeNotice] = useState<string>('')

  useEffect(() => {
    loadLogs()
  }, [severityFilter])

  const loadLogs = async () => {
    setLoading(true)
    try {
      const data = await complianceService.getAuditLogs({
        severity: severityFilter === 'all' ? undefined : severityFilter,
      })
      setLogs(data)
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async (format: 'json' | 'csv') => {
    setExporting(format)
    try {
      await complianceService.exportComplianceReport(format)
    } finally {
      setExporting(null)
    }
  }

  const handleGdprPurge = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!purgeEmail.trim()) return
    const res = await complianceService.gdprPurge(purgeEmail)
    setPurgeNotice(res.message)
    setShowGdprModal(false)
    setPurgeEmail('')
    loadLogs()
  }

  const severityColors: Record<string, { bg: string; text: string; border: string }> = {
    low: { bg: '#ecfdf5', text: '#059669', border: '#a7f3d0' },
    medium: { bg: '#eff6ff', text: '#2563eb', border: '#bfdbfe' },
    high: { bg: '#fffbeb', text: '#d97706', border: '#fde68a' },
    critical: { bg: '#fef2f2', text: '#dc2626', border: '#fecaca' },
  }

  return (
    <div className="anim-fade-up" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
          padding: '20px 24px',
          borderRadius: '14px',
          background: theme === 'dark' ? '#141124' : '#faf9fe',
          border: `1px solid ${theme === 'dark' ? '#261f42' : '#e9e6f2'}`,
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{ fontSize: '11px', fontWeight: 800, color: '#10b981', letterSpacing: '1px' }}>
              ● AUDIT VAULT ACTIVE
            </span>
            <span
              style={{
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: '12px',
                background: '#d1fae5',
                color: '#065f46',
                fontWeight: 700,
              }}
            >
              SOC2 Type II & GDPR Art. 17
            </span>
          </div>
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>Immutable Compliance Event Stream</h3>
          <p style={{ margin: '4px 0 0', color: '#888', fontSize: '13px' }}>
            All authentication attempts, biometric enrollments, meeting recordings, and data export events are cryptographically hashed and logged.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => handleExport('json')}
            disabled={exporting !== null}
            className="btn-anim"
            style={{
              padding: '8px 14px',
              borderRadius: '8px',
              border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
              background: 'transparent',
              color: 'inherit',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {exporting === 'json' ? 'Generating...' : '📥 Export JSON'}
          </button>
          <button
            type="button"
            onClick={() => handleExport('csv')}
            disabled={exporting !== null}
            className="btn-anim"
            style={{
              padding: '8px 14px',
              borderRadius: '8px',
              border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
              background: 'transparent',
              color: 'inherit',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {exporting === 'csv' ? 'Generating...' : '📊 Export CSV'}
          </button>
          <button
            type="button"
            onClick={() => setShowGdprModal(true)}
            className="btn-anim"
            style={{
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid #ef4444',
              background: '#ef4444',
              color: '#fff',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            🗑️ GDPR Purge
          </button>
        </div>
      </div>

      {purgeNotice && (
        <div
          style={{
            background: '#ecfdf5',
            color: '#065f46',
            padding: '10px 14px',
            borderRadius: '8px',
            fontSize: '13px',
            fontWeight: 600,
          }}
        >
          {purgeNotice}
        </div>
      )}

      {/* Severity Filter Pills */}
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <span style={{ fontSize: '12px', fontWeight: 700, color: '#888' }}>SEVERITY:</span>
        {['all', 'low', 'medium', 'high', 'critical'].map((sev) => (
          <button
            key={sev}
            type="button"
            onClick={() => setSeverityFilter(sev)}
            className="btn-anim"
            style={{
              padding: '4px 12px',
              borderRadius: '6px',
              fontSize: '12px',
              fontWeight: 600,
              textTransform: 'capitalize',
              border: severityFilter === sev ? '1px solid #7c3aed' : `1px solid ${theme === 'dark' ? '#332959' : '#e5e7eb'}`,
              background: severityFilter === sev ? (theme === 'dark' ? '#261f42' : '#ede9fe') : 'transparent',
              color: severityFilter === sev ? '#7c3aed' : 'inherit',
              cursor: 'pointer',
            }}
          >
            {sev}
          </button>
        ))}
      </div>

      {/* Audit Log Table */}
      <div
        style={{
          borderRadius: '12px',
          border: `1px solid ${theme === 'dark' ? '#261f42' : '#e5e7eb'}`,
          overflow: 'hidden',
          background: theme === 'dark' ? '#141124' : '#fff',
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '170px 1.2fr 1fr 120px 90px 80px',
            padding: '12px 16px',
            background: theme === 'dark' ? '#1a1630' : '#f9fafb',
            fontSize: '11px',
            fontWeight: 700,
            color: '#888',
            borderBottom: `1px solid ${theme === 'dark' ? '#261f42' : '#e5e7eb'}`,
          }}
        >
          <span>TIMESTAMP</span>
          <span>ACTION EVENT</span>
          <span>ACTOR</span>
          <span>IP TELEMETRY</span>
          <span>SEVERITY</span>
          <span>STATUS</span>
        </div>

        <div style={{ maxHeight: '420px', overflowY: 'auto' }}>
          {logs.map((log) => {
            const sc = severityColors[log.severity] || severityColors.low
            return (
              <div
                key={log.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '170px 1.2fr 1fr 120px 90px 80px',
                  padding: '12px 16px',
                  alignItems: 'center',
                  fontSize: '12px',
                  borderBottom: `1px solid ${theme === 'dark' ? '#1f1a38' : '#f3f4f6'}`,
                  transition: 'background-color 0.15s ease',
                }}
              >
                <span style={{ fontFamily: 'monospace', fontSize: '11px', color: '#888' }}>
                  {new Date(log.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'medium' })}
                </span>
                <span style={{ fontWeight: 600, fontFamily: 'monospace' }}>
                  {log.action}
                </span>
                <span style={{ color: theme === 'dark' ? '#c4b5fd' : '#4f46e5' }}>
                  {log.user_email}
                </span>
                <span style={{ fontFamily: 'monospace', fontSize: '11px', color: '#888' }}>
                  {log.ip_address}
                </span>
                <span>
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      padding: '2px 8px',
                      borderRadius: '6px',
                      background: sc.bg,
                      color: sc.text,
                      border: `1px solid ${sc.border}`,
                    }}
                  >
                    {log.severity}
                  </span>
                </span>
                <span>
                  <span style={{ color: '#10b981', fontWeight: 600 }}>✓ {log.status}</span>
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* GDPR Purge Modal */}
      {showGdprModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 10001,
            background: 'rgba(0,0,0,0.65)',
            backdropFilter: 'blur(4px)',
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
              maxWidth: '460px',
              background: theme === 'dark' ? '#18142a' : '#fff',
              color: theme === 'dark' ? '#f0eeff' : '#1f1b2e',
              borderRadius: '16px',
              padding: '24px',
              border: '1px solid #ef4444',
              boxShadow: '0 25px 50px rgba(0,0,0,0.4)',
            }}
          >
            <h3 style={{ margin: '0 0 10px', color: '#ef4444', fontSize: '18px' }}>
              GDPR Article 17 Data Erasure
            </h3>
            <p style={{ fontSize: '13px', color: '#888', lineHeight: 1.5, margin: '0 0 16px' }}>
              Executing this right-to-erasure action will permanently purge all transcripts, audio recordings, biometric voiceprints, and session metadata for the specified user email.
            </p>
            <form onSubmit={handleGdprPurge}>
              <label style={{ fontSize: '12px', fontWeight: 700, display: 'block', marginBottom: '6px' }}>
                CONFIRM TARGET EMAIL
              </label>
              <input
                type="email"
                required
                value={purgeEmail}
                onChange={(e) => setPurgeEmail(e.target.value)}
                placeholder="user@example.com"
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
                  background: theme === 'dark' ? '#141124' : '#fff',
                  color: 'inherit',
                  fontSize: '13px',
                  marginBottom: '16px',
                }}
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowGdprModal(false)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    border: '1px solid #888',
                    background: 'transparent',
                    color: 'inherit',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{
                    padding: '8px 18px',
                    borderRadius: '8px',
                    background: '#ef4444',
                    color: '#fff',
                    border: 'none',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Purge User Data
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

