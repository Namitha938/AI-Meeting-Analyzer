import React, { useState } from 'react'

export interface AgendaItem {
  id: string
  title: string
  allocatedMin: number
  isCompleted: boolean
  matchedQuote?: string
  coveredAtMin?: number
  status: 'covered' | 'in_progress' | 'skipped'
}

interface MeetingAgendaManagerProps {
  meeting: any
  theme: 'light' | 'dark'
}

const PRESET_TEMPLATES: Record<string, { title: string; icon: string; items: Omit<AgendaItem, 'id'>[] }> = {
  sprint_planning: {
    title: 'Sprint Planning & Backlog Sync',
    icon: '⚡',
    items: [
      { title: 'Sprint Goal & Objective Alignment', allocatedMin: 5, isCompleted: true, status: 'covered', coveredAtMin: 2, matchedQuote: 'Goal is finalizing the architecture specification.' },
      { title: 'Review Completed User Stories & Carryovers', allocatedMin: 10, isCompleted: true, status: 'covered', coveredAtMin: 7, matchedQuote: 'Reviewed API changes and PR handoffs.' },
      { title: 'Capacity & Velocity Estimation', allocatedMin: 10, isCompleted: true, status: 'covered', coveredAtMin: 14, matchedQuote: 'Marcus committed to API changes review by tomorrow.' },
      { title: 'Blocker & Risk Assessment', allocatedMin: 5, isCompleted: false, status: 'skipped', matchedQuote: 'Not explicitly raised during call.' },
    ],
  },
  one_on_one: {
    title: 'Weekly 1-on-1 Sync',
    icon: '👥',
    items: [
      { title: 'Personal Check-in & Well-being', allocatedMin: 5, isCompleted: true, status: 'covered', coveredAtMin: 1 },
      { title: 'Weekly Wins & Key Milestones', allocatedMin: 10, isCompleted: true, status: 'covered', coveredAtMin: 6 },
      { title: 'Current Roadblocks & Support Needed', allocatedMin: 10, isCompleted: true, status: 'covered', coveredAtMin: 15 },
      { title: 'Long-term Goals & Growth Plan', allocatedMin: 5, isCompleted: false, status: 'skipped' },
    ],
  },
  client_discovery: {
    title: 'Client Discovery & Requirements',
    icon: '💼',
    items: [
      { title: 'Introductions & Meeting Purpose', allocatedMin: 5, isCompleted: true, status: 'covered', coveredAtMin: 1 },
      { title: 'Customer Pain Points & Current Workflow', allocatedMin: 15, isCompleted: true, status: 'covered', coveredAtMin: 8 },
      { title: 'Technical Architecture & Security Requirements', allocatedMin: 15, isCompleted: true, status: 'covered', coveredAtMin: 18 },
      { title: 'Budget, Timelines & Next Decision Steps', allocatedMin: 10, isCompleted: true, status: 'covered', coveredAtMin: 24 },
    ],
  },
  design_critique: {
    title: 'Product Design & UI Critique',
    icon: '🎨',
    items: [
      { title: 'Design Problem Statement & User Persona', allocatedMin: 5, isCompleted: true, status: 'covered', coveredAtMin: 3 },
      { title: 'Interactive Prototype Walkthrough', allocatedMin: 15, isCompleted: true, status: 'covered', coveredAtMin: 9 },
      { title: 'Critique: Usability, Accessibility & Tokens', allocatedMin: 15, isCompleted: true, status: 'covered', coveredAtMin: 21 },
      { title: 'Actionable Handoff Decisions', allocatedMin: 5, isCompleted: true, status: 'covered', coveredAtMin: 28 },
    ],
  },
}

export const MeetingAgendaManager: React.FC<MeetingAgendaManagerProps> = ({ meeting, theme }) => {
  const isDark = theme === 'dark'
  const [selectedTemplateKey, setSelectedTemplateKey] = useState<string>('sprint_planning')
  const [agendaItems, setAgendaItems] = useState<AgendaItem[]>(() => {
    return PRESET_TEMPLATES.sprint_planning.items.map((item, i) => ({
      ...item,
      id: `item-${i}`,
    }))
  })
  const [newItemText, setNewItemText] = useState<string>('')
  const [newItemMinutes, setNewItemMinutes] = useState<number>(5)

  const bgCard = isDark ? '#1a162b' : '#ffffff'
  const borderCard = isDark ? '#2b2349' : '#e8e5ec'
  const textColor = isDark ? '#f4f2fa' : '#1e1b33'
  const subTextColor = isDark ? '#9e99ad' : '#6b7280'

  const handleSelectTemplate = (key: string) => {
    setSelectedTemplateKey(key)
    const tpl = PRESET_TEMPLATES[key]
    if (tpl) {
      setAgendaItems(
        tpl.items.map((item, i) => ({
          ...item,
          id: `item-${Date.now()}-${i}`,
        }))
      )
    }
  }

  const handleToggleItem = (id: string) => {
    setAgendaItems((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              isCompleted: !item.isCompleted,
              status: !item.isCompleted ? 'covered' : 'skipped',
            }
          : item
      )
    )
  }

  const handleAddItem = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newItemText.trim()) return
    setAgendaItems((prev) => [
      ...prev,
      {
        id: `custom-${Date.now()}`,
        title: newItemText.trim(),
        allocatedMin: newItemMinutes || 5,
        isCompleted: false,
        status: 'skipped',
      },
    ])
    setNewItemText('')
  }

  const totalAllocated = agendaItems.reduce((acc, curr) => acc + curr.allocatedMin, 0)
  const coveredCount = agendaItems.filter((i) => i.isCompleted || i.status === 'covered').length
  const completionPct = Math.round((coveredCount / Math.max(1, agendaItems.length)) * 100)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Template Selector Ribbon */}
      <div
        style={{
          background: bgCard,
          border: `1px solid ${borderCard}`,
          borderRadius: '12px',
          padding: '14px 18px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
        }}
      >
        <div>
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#6d55d8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Meeting Agenda Template
          </span>
          <h4 style={{ margin: '2px 0 0', fontSize: '15px', color: textColor }}>
            {PRESET_TEMPLATES[selectedTemplateKey]?.title || 'Custom Agenda'}
          </h4>
        </div>

        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {Object.entries(PRESET_TEMPLATES).map(([k, tpl]) => (
            <button
              key={k}
              type="button"
              onClick={() => handleSelectTemplate(k)}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                border: selectedTemplateKey === k ? '1px solid #7c67dc' : `1px solid ${borderCard}`,
                background: selectedTemplateKey === k ? (isDark ? '#2f245c' : '#ede9fe') : 'transparent',
                color: selectedTemplateKey === k ? '#7c67dc' : subTextColor,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                transition: 'all 0.15s ease',
              }}
            >
              <span>{tpl.icon}</span>
              <span>{tpl.title.split('&')[0].trim()}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Progress & Stats Bar */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '12px',
        }}
      >
        <div style={{ background: bgCard, border: `1px solid ${borderCard}`, borderRadius: '10px', padding: '12px 16px' }}>
          <span style={{ fontSize: '11px', color: subTextColor, textTransform: 'uppercase' }}>Agenda Coverage</span>
          <div style={{ fontSize: '20px', fontWeight: 800, color: completionPct >= 75 ? '#10b981' : '#f59e0b', marginTop: '2px' }}>
            {coveredCount} of {agendaItems.length} Topics ({completionPct}%)
          </div>
        </div>

        <div style={{ background: bgCard, border: `1px solid ${borderCard}`, borderRadius: '10px', padding: '12px 16px' }}>
          <span style={{ fontSize: '11px', color: subTextColor, textTransform: 'uppercase' }}>Allocated Duration</span>
          <div style={{ fontSize: '20px', fontWeight: 800, color: '#38bdf8', marginTop: '2px' }}>
            {totalAllocated} Minutes Planned
          </div>
        </div>

        <div style={{ background: bgCard, border: `1px solid ${borderCard}`, borderRadius: '10px', padding: '12px 16px' }}>
          <span style={{ fontSize: '11px', color: subTextColor, textTransform: 'uppercase' }}>AI Audit Status</span>
          <div style={{ fontSize: '14px', fontWeight: 700, color: '#a78bfa', marginTop: '4px' }}>
            ⚡ Grounded in Diarized Audio
          </div>
        </div>
      </div>

      {/* Agenda Items List */}
      <div
        style={{
          background: bgCard,
          border: `1px solid ${borderCard}`,
          borderRadius: '14px',
          padding: '20px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: textColor }}>
            Topics & Discussion Checklist
          </h4>
          <span style={{ fontSize: '11px', color: subTextColor }}>Click item to toggle status</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {agendaItems.map((item, idx) => {
            const isCovered = item.isCompleted || item.status === 'covered'
            return (
              <div
                key={item.id}
                onClick={() => handleToggleItem(item.id)}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  padding: '12px 16px',
                  borderRadius: '10px',
                  background: isCovered
                    ? (isDark ? '#192a20' : '#f0fdf4')
                    : (isDark ? '#231e3d' : '#f9f8fc'),
                  border: isCovered
                    ? '1px solid rgba(34, 197, 94, 0.4)'
                    : `1px solid ${borderCard}`,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                  <input
                    type="checkbox"
                    checked={isCovered}
                    onChange={() => handleToggleItem(item.id)}
                    style={{ marginTop: '3px', accentColor: '#22c55e', cursor: 'pointer', width: '16px', height: '16px' }}
                  />
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: isCovered ? (isDark ? '#86efac' : '#15803d') : textColor }}>
                      {idx + 1}. {item.title}
                    </div>
                    {item.matchedQuote && (
                      <div style={{ fontSize: '11px', color: subTextColor, marginTop: '3px', fontStyle: 'italic' }}>
                        💬 "{item.matchedQuote}"
                      </div>
                    )}
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
                  {item.coveredAtMin !== undefined && (
                    <span style={{ fontSize: '11px', fontWeight: 600, color: '#10b981', background: isDark ? '#14382c' : '#dcfce7', padding: '2px 8px', borderRadius: '4px' }}>
                      ⏱ Discussed at {item.coveredAtMin}:00
                    </span>
                  )}
                  <span style={{ fontSize: '11px', color: subTextColor, background: isDark ? '#2b2349' : '#e8e5ec', padding: '2px 6px', borderRadius: '4px' }}>
                    {item.allocatedMin}m
                  </span>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      background: isCovered ? '#22c55e' : '#f59e0b',
                      color: isCovered ? '#fff' : '#000',
                    }}
                  >
                    {isCovered ? 'Covered' : 'Skipped'}
                  </span>
                </div>
              </div>
            )
          })}
        </div>

        {/* Add Custom Agenda Item Form */}
        <form onSubmit={handleAddItem} style={{ display: 'flex', gap: '10px', marginTop: '16px', paddingTop: '16px', borderTop: `1px solid ${borderCard}` }}>
          <input
            type="text"
            placeholder="Add new agenda topic..."
            value={newItemText}
            onChange={(e) => setNewItemText(e.target.value)}
            style={{
              flex: 1,
              background: isDark ? '#13111f' : '#f4f2fa',
              border: `1px solid ${borderCard}`,
              borderRadius: '8px',
              padding: '8px 12px',
              fontSize: '13px',
              color: textColor,
            }}
          />
          <input
            type="number"
            min={1}
            max={60}
            value={newItemMinutes}
            onChange={(e) => setNewItemMinutes(Number(e.target.value))}
            title="Estimated minutes"
            style={{
              width: '70px',
              background: isDark ? '#13111f' : '#f4f2fa',
              border: `1px solid ${borderCard}`,
              borderRadius: '8px',
              padding: '8px',
              fontSize: '13px',
              color: textColor,
              textAlign: 'center',
            }}
          />
          <button
            type="submit"
            style={{
              background: '#7c67dc',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              padding: '8px 16px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            + Add Topic
          </button>
        </form>
      </div>
    </div>
  )
}
