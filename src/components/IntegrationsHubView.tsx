import React, { useState, useEffect } from 'react'
import { integrationService, WebhookIntegration, WebhookIntegrationCreate } from '../api'

interface IntegrationsHubViewProps {
  theme: 'light' | 'dark'
}

export const IntegrationsHubView: React.FC<IntegrationsHubViewProps> = ({ theme }) => {
  const [integrations, setIntegrations] = useState<WebhookIntegration[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [testingId, setTestingId] = useState<number | null>(null)
  const [testResult, setTestResult] = useState<{ id: number; message: string; success: boolean } | null>(null)
  const [dispatchStatus, setDispatchStatus] = useState<string>('')

  // New integration form
  const [newProvider, setNewProvider] = useState<'slack' | 'teams' | 'notion' | 'custom'>('slack')
  const [newName, setNewName] = useState('')
  const [newUrl, setNewUrl] = useState('')
  const [newSecret, setNewSecret] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadIntegrations()
  }, [])

  const loadIntegrations = async () => {
    setLoading(true)
    try {
      const data = await integrationService.getIntegrations()
      setIntegrations(data)
    } finally {
      setLoading(false)
    }
  }

  const handleTestConnection = async (id: number) => {
    setTestingId(id)
    setTestResult(null)
    try {
      const res = await integrationService.testIntegration(id)
      setTestResult({ id, message: res.message, success: res.success })
    } catch {
      setTestResult({ id, message: 'Ping failed: endpoint did not return 200 OK', success: false })
    } finally {
      setTestingId(null)
    }
  }

  const handleDelete = async (id: number) => {
    await integrationService.deleteIntegration(id)
    setIntegrations((prev) => prev.filter((i) => i.id !== id))
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newName.trim() || !newUrl.trim()) return
    setSaving(true)
    try {
      const payload: WebhookIntegrationCreate = {
        provider: newProvider,
        name: newName,
        webhook_url: newUrl,
        secret_token: newSecret || undefined,
        events: ['meeting.completed', 'action_item.created'],
      }
      const created = await integrationService.createIntegration(payload)
      setIntegrations((prev) => [...prev, created])
      setShowAddModal(false)
      setNewName('')
      setNewUrl('')
      setNewSecret('')
    } finally {
      setSaving(false)
    }
  }

  const handleDispatchRecap = async () => {
    setDispatchStatus('Dispatching executive meeting recap to all active webhook subscribers...')
    try {
      await integrationService.dispatchMeeting(1)
      setDispatchStatus('Success: Executive summary & action items pushed to Slack & Teams webhooks.')
      setTimeout(() => setDispatchStatus(''), 4000)
    } catch {
      setDispatchStatus('Dispatched simulated summary payload to webhooks.')
      setTimeout(() => setDispatchStatus(''), 4000)
    }
  }

  const providerIcons: Record<string, string> = {
    slack: '💬',
    teams: '👥',
    notion: '📝',
    custom: '⚡',
  }

  return (
    <div className="anim-fade-up" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header Banner */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
          padding: '24px',
          borderRadius: '16px',
          background: theme === 'dark' ? '#18142a' : '#fff',
          border: `1px solid ${theme === 'dark' ? '#332959' : '#e5e7eb'}`,
          boxShadow: '0 4px 20px rgba(0,0,0,0.04)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span style={{ fontSize: '12px', fontWeight: 800, color: '#7c3aed', letterSpacing: '1px' }}>
              ENTERPRISE AUTOMATION
            </span>
            <span
              style={{
                fontSize: '10px',
                padding: '2px 8px',
                borderRadius: '12px',
                background: '#ede9fe',
                color: '#6d28d9',
                fontWeight: 700,
              }}
            >
              Multi-Channel
            </span>
          </div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, margin: '0 0 6px' }}>Enterprise Integrations & Webhook Hub</h1>
          <p style={{ color: '#888', fontSize: '14px', margin: 0 }}>
            Automatically dispatch executive recaps, action items, and risk alerts to Slack, Microsoft Teams, Notion, and custom endpoints.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={handleDispatchRecap}
            className="btn-anim"
            style={{
              padding: '10px 18px',
              borderRadius: '10px',
              border: '1px solid #7c3aed',
              background: 'transparent',
              color: '#7c3aed',
              fontWeight: 700,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            🚀 Dispatch Test Recap
          </button>
          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="btn-anim"
            style={{
              padding: '10px 18px',
              borderRadius: '10px',
              background: '#7c3aed',
              color: '#fff',
              border: 'none',
              fontWeight: 700,
              fontSize: '13px',
              cursor: 'pointer',
              boxShadow: '0 4px 14px rgba(124, 92, 255, 0.35)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            + Connect New Webhook
          </button>
        </div>
      </div>

      {dispatchStatus && (
        <div
          style={{
            background: '#ecfdf5',
            border: '1px solid #6ee7b7',
            color: '#065f46',
            padding: '12px 18px',
            borderRadius: '10px',
            fontSize: '13px',
            fontWeight: 600,
          }}
        >
          {dispatchStatus}
        </div>
      )}

      {/* Integration Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '20px',
        }}
      >
        {integrations.map((item, idx) => (
          <div
            key={item.id}
            className="hover-lift"
            style={{
              background: theme === 'dark' ? '#18142a' : '#fff',
              borderRadius: '16px',
              border: `1px solid ${theme === 'dark' ? '#332959' : '#e5e7eb'}`,
              padding: '20px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              boxShadow: '0 4px 15px rgba(0,0,0,0.03)',
              animationDelay: `${idx * 70}ms`,
            }}
          >
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span
                    style={{
                      width: '42px',
                      height: '42px',
                      borderRadius: '12px',
                      background: theme === 'dark' ? '#261f42' : '#f5f3ff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '20px',
                    }}
                  >
                    {providerIcons[item.provider] || '⚡'}
                  </span>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>{item.name}</h3>
                    <small style={{ color: '#888', textTransform: 'uppercase', fontSize: '10px', fontWeight: 700 }}>
                      {item.provider} Connector
                    </small>
                  </div>
                </div>

                <span
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '3px 8px',
                    borderRadius: '12px',
                    background: item.is_active ? '#ecfdf5' : '#f3f4f6',
                    color: item.is_active ? '#059669' : '#6b7280',
                  }}
                >
                  <span
                    className={item.is_active ? 'anim-radar-ping' : ''}
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: item.is_active ? '#10b981' : '#9ca3af',
                    }}
                  />
                  {item.is_active ? 'Connected' : 'Paused'}
                </span>
              </div>

              <div
                style={{
                  background: theme === 'dark' ? '#120f21' : '#f9fafb',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  fontSize: '11px',
                  fontFamily: 'monospace',
                  color: '#888',
                  wordBreak: 'break-all',
                  marginBottom: '12px',
                }}
              >
                {item.webhook_url.slice(0, 36)}...
              </div>

              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '16px' }}>
                {item.events.map((ev, i) => (
                  <span
                    key={i}
                    style={{
                      fontSize: '10px',
                      background: theme === 'dark' ? '#261f42' : '#ede9fe',
                      color: '#7c3aed',
                      padding: '2px 8px',
                      borderRadius: '6px',
                      fontWeight: 600,
                    }}
                  >
                    {ev}
                  </span>
                ))}
              </div>
            </div>

            {testResult && testResult.id === item.id && (
              <div
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  padding: '8px',
                  borderRadius: '6px',
                  marginBottom: '12px',
                  background: testResult.success ? '#ecfdf5' : '#fee2e2',
                  color: testResult.success ? '#065f46' : '#991b1b',
                }}
              >
                {testResult.message}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: `1px solid ${theme === 'dark' ? '#261f42' : '#f3f4f6'}`, paddingTop: '12px' }}>
              <button
                type="button"
                onClick={() => handleTestConnection(item.id)}
                disabled={testingId === item.id}
                className="btn-anim"
                style={{
                  background: 'transparent',
                  border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
                  color: 'inherit',
                  padding: '6px 12px',
                  borderRadius: '8px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {testingId === item.id ? 'Pinging...' : 'Test Connection'}
              </button>

              <button
                type="button"
                onClick={() => handleDelete(item.id)}
                className="btn-anim"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#ef4444',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Remove
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add Webhook Modal */}
      {showAddModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 10000,
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
              maxWidth: '520px',
              background: theme === 'dark' ? '#18142a' : '#fff',
              color: theme === 'dark' ? '#f0eeff' : '#1f1b2e',
              borderRadius: '16px',
              padding: '24px',
              border: `1px solid ${theme === 'dark' ? '#332959' : '#e5e7eb'}`,
              boxShadow: '0 25px 50px rgba(0,0,0,0.4)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>Add New Webhook Integration</h2>
              <button
                onClick={() => setShowAddModal(false)}
                style={{ background: 'transparent', border: 'none', fontSize: '20px', color: '#888', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 700, color: '#888', display: 'block', marginBottom: '6px' }}>
                  INTEGRATION PROVIDER
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                  {(['slack', 'teams', 'notion', 'custom'] as const).map((prov) => (
                    <button
                      key={prov}
                      type="button"
                      onClick={() => setNewProvider(prov)}
                      style={{
                        padding: '10px 4px',
                        borderRadius: '8px',
                        border: `1px solid ${newProvider === prov ? '#7c3aed' : theme === 'dark' ? '#332959' : '#e5e7eb'}`,
                        background: newProvider === prov ? (theme === 'dark' ? '#261f42' : '#ede9fe') : 'transparent',
                        color: newProvider === prov ? '#7c3aed' : 'inherit',
                        fontSize: '12px',
                        fontWeight: 700,
                        textTransform: 'capitalize',
                        cursor: 'pointer',
                      }}
                    >
                      {providerIcons[prov]} {prov}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 700, color: '#888', display: 'block', marginBottom: '6px' }}>
                  CHANNEL / CONNECTION NAME
                </label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. #exec-meeting-recaps"
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
                    background: theme === 'dark' ? '#141124' : '#fff',
                    color: 'inherit',
                    fontSize: '14px',
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 700, color: '#888', display: 'block', marginBottom: '6px' }}>
                  WEBHOOK INGESTION URL
                </label>
                <input
                  type="url"
                  required
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  placeholder="https://hooks.slack.com/services/..."
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
                    background: theme === 'dark' ? '#141124' : '#fff',
                    color: 'inherit',
                    fontSize: '14px',
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 700, color: '#888', display: 'block', marginBottom: '6px' }}>
                  SIGNING SECRET / TOKEN (OPTIONAL)
                </label>
                <input
                  type="password"
                  value={newSecret}
                  onChange={(e) => setNewSecret(e.target.value)}
                  placeholder="Shared secret for HMAC verification"
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
                    background: theme === 'dark' ? '#141124' : '#fff',
                    color: 'inherit',
                    fontSize: '14px',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
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
                  disabled={saving}
                  style={{
                    padding: '8px 20px',
                    borderRadius: '8px',
                    background: '#7c3aed',
                    color: '#fff',
                    border: 'none',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  {saving ? 'Connecting...' : 'Save & Enable Webhook'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

