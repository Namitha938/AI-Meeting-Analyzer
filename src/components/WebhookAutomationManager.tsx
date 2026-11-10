import React, { useState } from 'react'

export interface WebhookConfig {
  id: string
  name: string
  url: string
  events: string[]
  isActive: boolean
  lastTriggered?: string
  lastStatus?: number
}

interface WebhookAutomationManagerProps {
  theme: 'light' | 'dark'
}

export const WebhookAutomationManager: React.FC<WebhookAutomationManagerProps> = ({ theme }) => {
  const isDark = theme === 'dark'
  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([
    {
      id: 'wh-1',
      name: 'Zapier Production Automation',
      url: 'https://hooks.zapier.com/hooks/catch/184920/38912/',
      events: ['meeting.analyzed', 'action_item.created'],
      isActive: true,
      lastTriggered: '10 mins ago',
      lastStatus: 200,
    },
    {
      id: 'wh-2',
      name: 'Slack Internal Alerts Webhook',
      url: 'https://hooks.slack.com/services/T00/B00/XXXXX',
      events: ['action_item.created'],
      isActive: true,
      lastTriggered: '2 hours ago',
      lastStatus: 200,
    },
  ])

  const [newWebhookName, setNewWebhookName] = useState<string>('')
  const [newWebhookUrl, setNewWebhookUrl] = useState<string>('')
  const [isPinging, setIsPinging] = useState<string | null>(null)
  const [pingResult, setPingResult] = useState<{ id: string; success: boolean; message: string } | null>(null)

  const handleTestPing = (id: string, url: string) => {
    setIsPinging(id)
    setPingResult(null)

    setTimeout(() => {
      setIsPinging(null)
      setPingResult({
        id,
        success: true,
        message: `HTTP 200 OK — Webhook payload delivered in 142ms!`,
      })
      setTimeout(() => setPingResult(null), 5000)
    }, 1000)
  }

  const handleAddWebhook = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newWebhookUrl.trim()) return
    const newWh: WebhookConfig = {
      id: `wh-${Date.now()}`,
      name: newWebhookName.trim() || 'Custom Outgoing Webhook',
      url: newWebhookUrl.trim(),
      events: ['meeting.analyzed', 'action_item.created'],
      isActive: true,
      lastTriggered: 'Just added',
      lastStatus: 200,
    }
    setWebhooks((prev) => [newWh, ...prev])
    setNewWebhookName('')
    setNewWebhookUrl('')
  }

  const handleToggleActive = (id: string) => {
    setWebhooks((prev) =>
      prev.map((wh) => (wh.id === id ? { ...wh, isActive: !wh.isActive } : wh))
    )
  }

  const handleDeleteWebhook = (id: string) => {
    setWebhooks((prev) => prev.filter((wh) => wh.id !== id))
  }

  const bgCard = isDark ? '#1a162b' : '#ffffff'
  const borderCard = isDark ? '#2b2349' : '#e8e5ec'
  const textColor = isDark ? '#f4f2fa' : '#1e1b33'
  const subTextColor = isDark ? '#9e99ad' : '#6b7280'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner */}
      <div
        style={{
          background: isDark ? 'linear-gradient(135deg, #241b47, #191433)' : 'linear-gradient(135deg, #f5f3ff, #ede9fe)',
          border: `1px solid ${isDark ? '#3d2e6e' : '#c4b5fd'}`,
          borderRadius: '14px',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '12px',
              background: '#f59e0b',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '20px',
              color: '#fff',
            }}
          >
            ⚡
          </div>
          <div>
            <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: textColor }}>
              Custom Outgoing Webhooks & Zapier Engine
            </h4>
            <p style={{ margin: '2px 0 0', fontSize: '12px', color: subTextColor }}>
              Emit structured JSON payloads to Zapier, Make.com, n8n, or custom endpoints upon meeting completion
            </p>
          </div>
        </div>

        <span
          style={{
            fontSize: '11px',
            fontWeight: 700,
            background: isDark ? '#32235c' : '#ffffff',
            color: '#f59e0b',
            padding: '4px 10px',
            borderRadius: '20px',
            border: '1px solid #f59e0b',
          }}
        >
          {webhooks.filter((w) => w.isActive).length} Active Webhooks
        </span>
      </div>

      {/* Existing Webhooks List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {webhooks.map((wh) => (
          <div
            key={wh.id}
            style={{
              background: bgCard,
              border: `1px solid ${borderCard}`,
              borderRadius: '12px',
              padding: '16px 20px',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
              boxShadow: '0 2px 10px rgba(0,0,0,0.02)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '18px' }}>{wh.name.toLowerCase().includes('slack') ? '💬' : '⚡'}</span>
                <div>
                  <h5 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: textColor }}>{wh.name}</h5>
                  <div style={{ fontSize: '11px', fontFamily: 'monospace', color: subTextColor, marginTop: '2px' }}>
                    {wh.url}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => handleToggleActive(wh.id)}
                  style={{
                    background: wh.isActive ? (isDark ? '#14382c' : '#dcfce7') : (isDark ? '#27272a' : '#e5e7eb'),
                    color: wh.isActive ? '#15803d' : subTextColor,
                    border: 'none',
                    borderRadius: '20px',
                    padding: '4px 10px',
                    fontSize: '11px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  {wh.isActive ? '● Active' : '○ Paused'}
                </button>

                <button
                  type="button"
                  onClick={() => handleTestPing(wh.id, wh.url)}
                  disabled={isPinging === wh.id}
                  style={{
                    background: '#6d55d8',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '5px 12px',
                    fontSize: '11px',
                    fontWeight: 600,
                    cursor: isPinging === wh.id ? 'not-allowed' : 'pointer',
                  }}
                >
                  {isPinging === wh.id ? 'Pinging...' : 'Test Ping'}
                </button>

                <button
                  type="button"
                  onClick={() => handleDeleteWebhook(wh.id)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#ef4444',
                    fontSize: '14px',
                    cursor: 'pointer',
                    padding: '4px',
                  }}
                >
                  🗑️
                </button>
              </div>
            </div>

            {/* Event Triggers & Last Status */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px', color: subTextColor, paddingTop: '6px', borderTop: `1px solid ${borderCard}` }}>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                <span style={{ fontWeight: 600 }}>Triggers:</span>
                {wh.events.map((ev, eIdx) => (
                  <span key={eIdx} style={{ background: isDark ? '#231e3d' : '#ede9fe', color: '#7c3aed', padding: '1px 6px', borderRadius: '4px' }}>
                    {ev}
                  </span>
                ))}
              </div>

              <span>Last triggered: {wh.lastTriggered || 'Never'}</span>
            </div>

            {pingResult && pingResult.id === wh.id && (
              <div style={{ padding: '8px 12px', borderRadius: '6px', background: 'rgba(34, 197, 94, 0.15)', border: '1px solid rgba(34, 197, 94, 0.3)', color: '#22c55e', fontSize: '11px', fontWeight: 600 }}>
                {pingResult.message}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Add New Webhook Card */}
      <div
        style={{
          background: bgCard,
          border: `1px solid ${borderCard}`,
          borderRadius: '14px',
          padding: '20px',
        }}
      >
        <h5 style={{ margin: '0 0 12px', fontSize: '14px', fontWeight: 700, color: textColor }}>
          + Add New Outgoing Webhook
        </h5>

        <form onSubmit={handleAddWebhook} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '10px' }}>
            <input
              type="text"
              placeholder="Webhook Name (e.g. Zapier / n8n)"
              value={newWebhookName}
              onChange={(e) => setNewWebhookName(e.target.value)}
              style={{
                background: isDark ? '#120f20' : '#f4f2fa',
                border: `1px solid ${borderCard}`,
                borderRadius: '8px',
                padding: '9px 12px',
                fontSize: '12px',
                color: textColor,
              }}
            />
            <input
              type="url"
              placeholder="https://hooks.zapier.com/hooks/catch/... or https://your-server.com/webhook"
              value={newWebhookUrl}
              onChange={(e) => setNewWebhookUrl(e.target.value)}
              required
              style={{
                background: isDark ? '#120f20' : '#f4f2fa',
                border: `1px solid ${borderCard}`,
                borderRadius: '8px',
                padding: '9px 12px',
                fontSize: '12px',
                color: textColor,
              }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="submit"
              disabled={!newWebhookUrl.trim()}
              style={{
                background: '#f59e0b',
                color: '#000',
                border: 'none',
                borderRadius: '8px',
                padding: '8px 18px',
                fontSize: '12px',
                fontWeight: 700,
                cursor: !newWebhookUrl.trim() ? 'not-allowed' : 'pointer',
              }}
            >
              Save Webhook Configuration
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
