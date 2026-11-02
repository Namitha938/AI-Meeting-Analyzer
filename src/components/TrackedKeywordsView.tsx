import React, { useState, useEffect } from 'react'
import { complianceService, TrackedKeyword, KeywordAnalysis, TrackedKeywordCreate } from '../api'

interface TrackedKeywordsViewProps {
  theme: 'light' | 'dark'
}

export const TrackedKeywordsView: React.FC<TrackedKeywordsViewProps> = ({ theme }) => {
  const [keywords, setKeywords] = useState<TrackedKeyword[]>([])
  const [analysis, setAnalysis] = useState<KeywordAnalysis[]>([])
  const [loading, setLoading] = useState(true)
  const [newWord, setNewWord] = useState('')
  const [newCategory, setNewCategory] = useState<'risk' | 'pricing' | 'competitor' | 'churn' | 'security' | 'general'>('risk')
  const [newColor, setNewColor] = useState('violet')
  const [activeAnalysis, setActiveAnalysis] = useState<KeywordAnalysis | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [kw, an] = await Promise.all([
        complianceService.getKeywords(),
        complianceService.getKeywordAnalysis(),
      ])
      setKeywords(kw)
      setAnalysis(an)
      if (an.length > 0) setActiveAnalysis(an[0])
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newWord.trim()) return
    const payload: TrackedKeywordCreate = {
      keyword: newWord.trim().toLowerCase(),
      category: newCategory,
      color: newColor,
      alert_enabled: true,
    }
    const created = await complianceService.addKeyword(payload)
    setKeywords((prev) => [...prev, created])
    setNewWord('')
    loadData()
  }

  const handleDelete = async (id: number) => {
    await complianceService.deleteKeyword(id)
    setKeywords((prev) => prev.filter((k) => k.id !== id))
    setAnalysis((prev) => prev.filter((a) => a.keyword_id !== id))
  }

  const categoryBadges: Record<string, { bg: string; color: string }> = {
    risk: { bg: '#fee2e2', color: '#991b1b' },
    pricing: { bg: '#e0e7ff', color: '#3730a3' },
    competitor: { bg: '#ffedd5', color: '#9a3412' },
    churn: { bg: '#fef2f2', color: '#b91c1c' },
    security: { bg: '#f3e8ff', color: '#6b21a8' },
    general: { bg: '#f3f4f6', color: '#374151' },
  }

  return (
    <div className="anim-fade-up" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          padding: '20px 24px',
          borderRadius: '14px',
          background: theme === 'dark' ? '#141124' : '#faf9fe',
          border: `1px solid ${theme === 'dark' ? '#261f42' : '#e9e6f2'}`,
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{ fontSize: '11px', fontWeight: 800, color: '#f59e0b', letterSpacing: '1px' }}>
              ● REAL-TIME RISK TRACKING
            </span>
            <span
              style={{
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: '12px',
                background: '#fef3c7',
                color: '#92400e',
                fontWeight: 700,
              }}
            >
              Watchlist Engine
            </span>
          </div>
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>Monitored Keywords & Risk Alerts</h3>
          <p style={{ margin: '4px 0 0', color: '#888', fontSize: '13px' }}>
            Track critical signals across transcripts: customer churn risks, competitor mentions, pricing pressure, and security compliance.
          </p>
        </div>
      </div>

      {/* Add New Keyword Bar */}
      <form
        onSubmit={handleAdd}
        style={{
          display: 'flex',
          gap: '10px',
          flexWrap: 'wrap',
          padding: '16px',
          borderRadius: '12px',
          background: theme === 'dark' ? '#18142a' : '#fff',
          border: `1px solid ${theme === 'dark' ? '#261f42' : '#e5e7eb'}`,
          alignItems: 'center',
        }}
      >
        <input
          type="text"
          required
          value={newWord}
          onChange={(e) => setNewWord(e.target.value)}
          placeholder="New keyword to track (e.g. churn, competitor, discount)..."
          style={{
            flex: 1,
            minWidth: '220px',
            padding: '9px 14px',
            borderRadius: '8px',
            border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
            background: theme === 'dark' ? '#141124' : '#fff',
            color: 'inherit',
            fontSize: '13px',
          }}
        />

        <select
          value={newCategory}
          onChange={(e) => setNewCategory(e.target.value as any)}
          style={{
            padding: '9px 12px',
            borderRadius: '8px',
            border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
            background: theme === 'dark' ? '#141124' : '#fff',
            color: 'inherit',
            fontSize: '13px',
          }}
        >
          <option value="risk">Risk Alert</option>
          <option value="pricing">Pricing & Commercial</option>
          <option value="competitor">Competitor Intel</option>
          <option value="churn">Churn Warning</option>
          <option value="security">Security & Compliance</option>
          <option value="general">General</option>
        </select>

        <select
          value={newColor}
          onChange={(e) => setNewColor(e.target.value)}
          style={{
            padding: '9px 12px',
            borderRadius: '8px',
            border: `1px solid ${theme === 'dark' ? '#332959' : '#d1d5db'}`,
            background: theme === 'dark' ? '#141124' : '#fff',
            color: 'inherit',
            fontSize: '13px',
          }}
        >
          <option value="violet">Purple</option>
          <option value="blue">Blue</option>
          <option value="orange">Orange</option>
          <option value="red">Red</option>
          <option value="emerald">Emerald</option>
        </select>

        <button
          type="submit"
          className="btn-anim"
          style={{
            padding: '9px 18px',
            borderRadius: '8px',
            background: '#7c3aed',
            color: '#fff',
            border: 'none',
            fontSize: '13px',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          + Track Keyword
        </button>
      </form>

      {/* Keywords Chips Grid */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {keywords.map((kw) => {
          const badge = categoryBadges[kw.category] || categoryBadges.general
          const isSelected = activeAnalysis?.keyword_id === kw.id
          return (
            <div
              key={kw.id}
              onClick={() => {
                const match = analysis.find((a) => a.keyword_id === kw.id)
                if (match) setActiveAnalysis(match)
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 12px',
                borderRadius: '20px',
                border: isSelected ? '2px solid #7c3aed' : `1px solid ${theme === 'dark' ? '#332959' : '#e5e7eb'}`,
                background: theme === 'dark' ? '#18142a' : '#fff',
                cursor: 'pointer',
                boxShadow: isSelected ? '0 0 12px rgba(124, 92, 255, 0.3)' : 'none',
              }}
            >
              <span style={{ fontWeight: 700, fontSize: '13px' }}>#{kw.keyword}</span>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  padding: '2px 6px',
                  borderRadius: '10px',
                  background: badge.bg,
                  color: badge.color,
                  textTransform: 'uppercase',
                }}
              >
                {kw.category}
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  handleDelete(kw.id)
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#888',
                  fontSize: '13px',
                  cursor: 'pointer',
                  padding: 0,
                }}
                title="Remove keyword"
              >
                ✕
              </button>
            </div>
          )
        })}
      </div>

      {/* Analysis Details Panel */}
      {activeAnalysis && (
        <div
          style={{
            background: theme === 'dark' ? '#141124' : '#fff',
            borderRadius: '14px',
            border: `1px solid ${theme === 'dark' ? '#261f42' : '#e5e7eb'}`,
            padding: '20px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h4 style={{ margin: 0, fontSize: '16px', fontWeight: 700 }}>
                Keyword Insight: #{activeAnalysis.keyword}
              </h4>
              <span
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  padding: '3px 10px',
                  borderRadius: '12px',
                  background: '#ede9fe',
                  color: '#7c3aed',
                }}
              >
                {activeAnalysis.mention_count} total occurrences detected
              </span>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {activeAnalysis.recent_mentions.map((m, i) => (
              <div
                key={i}
                style={{
                  padding: '12px 16px',
                  borderRadius: '10px',
                  background: theme === 'dark' ? '#1a1630' : '#f9fafb',
                  border: `1px solid ${theme === 'dark' ? '#261f42' : '#eee'}`,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '12px',
                }}
              >
                <div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontWeight: 700, fontSize: '13px' }}>{m.meeting_title}</span>
                    <span style={{ fontSize: '11px', color: '#7c3aed', fontWeight: 600 }}>• {m.speaker}</span>
                    <span style={{ fontSize: '11px', color: '#888', fontFamily: 'monospace' }}>[{m.timestamp_str}]</span>
                  </div>
                  <p style={{ margin: 0, fontSize: '13px', color: theme === 'dark' ? '#c4b5fd' : '#4b5563', fontStyle: 'italic' }}>
                    "{m.snippet}"
                  </p>
                </div>
                <span
                  style={{
                    fontSize: '11px',
                    padding: '4px 10px',
                    borderRadius: '8px',
                    background: '#ede9fe',
                    color: '#7c3aed',
                    fontWeight: 700,
                    flexShrink: 0,
                  }}
                >
                  Jump to transcript
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

