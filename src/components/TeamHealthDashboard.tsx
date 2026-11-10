import React, { useState } from 'react'

interface TeamHealthDashboardProps {
  theme: 'light' | 'dark'
}

export const TeamHealthDashboard: React.FC<TeamHealthDashboardProps> = ({ theme }) => {
  const isDark = theme === 'dark'
  const [hourlyRate, setHourlyRate] = useState<number>(65)
  const [showCostExplainer, setShowCostExplainer] = useState<boolean>(false)

  // Calculations for meeting cost
  const totalWeeklyMinutes = 840 // 14 hours
  const averageAttendeesPerCall = 4.2
  const totalCalls = 18
  const estimatedCost = Math.round((totalWeeklyMinutes / 60) * averageAttendeesPerCall * hourlyRate)
  const potentialSavingsMinutes = 180 // 3 hours
  const potentialSavingsDollars = Math.round((potentialSavingsMinutes / 60) * averageAttendeesPerCall * hourlyRate)

  const bgCard = isDark ? '#1a162b' : '#ffffff'
  const borderCard = isDark ? '#2b2349' : '#e8e5ec'
  const textColor = isDark ? '#f4f2fa' : '#1e1b33'
  const subTextColor = isDark ? '#9e99ad' : '#6b7280'

  const teamMemberLoad = [
    { name: 'Sarah Kim', hours: 16.5, calls: 14, risk: 'High', color: '#ef4444' },
    { name: 'Marcus Lee', hours: 12.0, calls: 10, risk: 'Moderate', color: '#f59e0b' },
    { name: 'Alex Lin', hours: 8.5, calls: 7, risk: 'Optimal', color: '#10b981' },
    { name: 'Jordan Davis', hours: 6.0, calls: 5, risk: 'Optimal', color: '#10b981' },
  ]

  const recurringTopics = [
    { tag: 'Architecture & Scalability', count: 9, weight: 1.4 },
    { tag: 'API Schema Validation', count: 7, weight: 1.2 },
    { tag: 'Sprint 24 Milestones', count: 6, weight: 1.1 },
    { tag: 'Security & Auth Compliance', count: 4, weight: 0.9 },
    { tag: 'Client Feature Requests', count: 4, weight: 0.9 },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner */}
      <div
        style={{
          background: isDark ? 'linear-gradient(135deg, #241b47, #191433)' : 'linear-gradient(135deg, #f5f3ff, #ede9fe)',
          border: `1px solid ${isDark ? '#3d2e6e' : '#c4b5fd'}`,
          borderRadius: '14px',
          padding: '18px 24px',
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
              background: '#10b981',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '20px',
              color: '#fff',
            }}
          >
            🩺
          </div>
          <div>
            <h4 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: textColor }}>
              Team Meeting Health & Coaching Dashboard
            </h4>
            <p style={{ margin: '2px 0 0', fontSize: '12px', color: subTextColor }}>
              Workplace intelligence: meeting overload warnings, brevity coaching, and financial cost estimation
            </p>
          </div>
        </div>

        <span
          style={{
            fontSize: '11px',
            fontWeight: 700,
            background: isDark ? '#14382c' : '#dcfce7',
            color: '#15803d',
            padding: '5px 12px',
            borderRadius: '20px',
            border: '1px solid #10b981',
          }}
        >
          Overall Health: Good (82/100)
        </span>
      </div>

      {/* KPI Cards: Hours, Cost, Brevity, Accountability */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        {/* Weekly Hours */}
        <div style={{ background: bgCard, border: `1px solid ${borderCard}`, borderRadius: '14px', padding: '18px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: subTextColor, textTransform: 'uppercase' }}>Weekly Meeting Time</span>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#7c67dc', margin: '4px 0' }}>
            14.0 <span style={{ fontSize: '13px', fontWeight: 500 }}>Hours</span>
          </div>
          <div style={{ fontSize: '11px', color: '#10b981' }}>
            ↓ 1.5 hrs lower than last week
          </div>
        </div>

        {/* Financial Cost */}
        <div style={{ background: bgCard, border: `1px solid ${borderCard}`, borderRadius: '14px', padding: '18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: subTextColor, textTransform: 'uppercase' }}>Estimated Weekly Cost</span>
            <button
              type="button"
              onClick={() => setShowCostExplainer(!showCostExplainer)}
              style={{ background: 'none', border: 'none', color: '#7c67dc', fontSize: '12px', cursor: 'pointer', padding: 0 }}
            >
              ⚙️
            </button>
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#f59e0b', margin: '4px 0' }}>
            ${estimatedCost.toLocaleString()}
          </div>
          <div style={{ fontSize: '11px', color: subTextColor }}>
            Based on ${hourlyRate}/hr average employee rate
          </div>
        </div>

        {/* Brevity Savings Opportunity */}
        <div style={{ background: bgCard, border: `1px solid ${borderCard}`, borderRadius: '14px', padding: '18px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: subTextColor, textTransform: 'uppercase' }}>Brevity Opportunity</span>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#10b981', margin: '4px 0' }}>
            +${potentialSavingsDollars.toLocaleString()}
          </div>
          <div style={{ fontSize: '11px', color: '#10b981' }}>
            By trimming ~10 min from recurring syncs
          </div>
        </div>

        {/* Action Item Follow-Through */}
        <div style={{ background: bgCard, border: `1px solid ${borderCard}`, borderRadius: '14px', padding: '18px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: subTextColor, textTransform: 'uppercase' }}>Task Follow-Through</span>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#38bdf8', margin: '4px 0' }}>
            88%
          </div>
          <div style={{ fontSize: '11px', color: '#38bdf8' }}>
            22 of 25 action items resolved on time
          </div>
        </div>
      </div>

      {/* Cost Calculator Settings Drawer */}
      {showCostExplainer && (
        <div style={{ background: bgCard, border: `1px solid ${borderCard}`, borderRadius: '12px', padding: '16px', display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1 }}>
            <h5 style={{ margin: 0, fontSize: '13px', color: textColor }}>Configure Average Team Hourly Compensation Rate:</h5>
            <small style={{ color: subTextColor }}>Used to calculate real-world meeting overhead and efficiency savings</small>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: textColor }}>$</span>
            <input
              type="number"
              value={hourlyRate}
              onChange={(e) => setHourlyRate(Number(e.target.value) || 25)}
              style={{ width: '80px', padding: '6px 10px', borderRadius: '6px', border: `1px solid ${borderCard}`, background: isDark ? '#120f20' : '#fff', color: textColor }}
            />
            <span style={{ fontSize: '12px', color: subTextColor }}>/ hour</span>
          </div>
        </div>
      )}

      {/* Two Column Layout: Overload Warning & Topic Cloud */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* Team Member Load & Fatigue Guard */}
        <div style={{ background: bgCard, border: `1px solid ${borderCard}`, borderRadius: '14px', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <div>
              <h5 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: textColor }}>
                Team Meeting Load & Burnout Guard
              </h5>
              <span style={{ fontSize: '11px', color: subTextColor }}>Hours in calls this week</span>
            </div>
            <span style={{ fontSize: '11px', background: '#fee2e2', color: '#991b1b', fontWeight: 700, padding: '2px 8px', borderRadius: '6px' }}>
              1 Alert
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {teamMemberLoad.map((member, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  background: isDark ? '#231e3d' : '#f9f8fc',
                }}
              >
                <div>
                  <b style={{ fontSize: '13px', color: textColor }}>{member.name}</b>
                  <div style={{ fontSize: '11px', color: subTextColor, marginTop: '2px' }}>
                    {member.calls} calls • {member.hours} hrs in meetings
                  </div>
                </div>

                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '3px 8px',
                    borderRadius: '6px',
                    background: member.risk === 'High' ? '#fee2e2' : member.risk === 'Moderate' ? '#fef3c7' : '#dcfce7',
                    color: member.risk === 'High' ? '#991b1b' : member.risk === 'Moderate' ? '#b45309' : '#166534',
                  }}
                >
                  {member.risk} Load
                </span>
              </div>
            ))}
          </div>

          <div style={{ marginTop: '14px', padding: '10px', borderRadius: '8px', background: isDark ? '#2d1f2b' : '#fff1f2', border: '1px solid #fecdd3', fontSize: '11px', color: '#e11d48' }}>
            ⚠️ <strong>Fatigue Warning:</strong> Sarah Kim is scheduled for 16.5 hours of meetings (41% of work week). Suggest delegating tomorrow's sync.
          </div>
        </div>

        {/* Recurring Topic Cloud */}
        <div style={{ background: bgCard, border: `1px solid ${borderCard}`, borderRadius: '14px', padding: '20px' }}>
          <h5 style={{ margin: '0 0 4px', fontSize: '14px', fontWeight: 700, color: textColor }}>
            Recurring Agenda Topics (Cross-Meeting Trends)
          </h5>
          <span style={{ fontSize: '11px', color: subTextColor, display: 'block', marginBottom: '14px' }}>
            Most frequent subjects discussed across team syncs
          </span>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {recurringTopics.map((topic, idx) => (
              <span
                key={idx}
                style={{
                  fontSize: `${11 + topic.count * 0.4}px`,
                  fontWeight: 600,
                  padding: '6px 12px',
                  borderRadius: '20px',
                  background: isDark ? '#231e3d' : '#f4f2fa',
                  border: `1px solid ${borderCard}`,
                  color: '#7c67dc',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>🏷️ {topic.tag}</span>
                <small style={{ color: subTextColor, fontSize: '10px' }}>({topic.count}x)</small>
              </span>
            ))}
          </div>

          <div style={{ marginTop: '20px', padding: '12px', borderRadius: '8px', background: isDark ? '#14382c' : '#f0fdf4', border: '1px solid #86efac', fontSize: '11px', color: '#166534' }}>
            💡 <strong>AI Coaching Tip:</strong> "Architecture & Scalability" has appeared in 9 meetings. Consider holding a single dedicated RFC review session to unblock pending decisions.
          </div>
        </div>
      </div>
    </div>
  )
}
