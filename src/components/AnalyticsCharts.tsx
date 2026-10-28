import React from 'react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from 'recharts'

interface AnalyticsChartsProps {
  theme: 'light' | 'dark'
  distribution?: Record<string, number>
}

export const AnalyticsCharts: React.FC<AnalyticsChartsProps> = ({ theme, distribution }) => {
  const isDark = theme === 'dark'

  const weeklyActivity = [
    { day: 'Mon', minutes: 85, meetings: 2 },
    { day: 'Tue', minutes: 120, meetings: 3 },
    { day: 'Wed', minutes: 65, meetings: 1 },
    { day: 'Thu', minutes: 145, meetings: 4 },
    { day: 'Fri', minutes: 90, meetings: 2 },
    { day: 'Sat', minutes: 0, meetings: 0 },
    { day: 'Sun', minutes: 30, meetings: 1 },
  ]

  const speakerData = distribution
    ? Object.entries(distribution).map(([name, pct]) => ({ name, value: pct }))
    : [
        { name: 'Sarah Kim', value: 45 },
        { name: 'Marcus Lee', value: 35 },
        { name: 'Jordan Davis', value: 20 },
      ]

  const COLORS = ['#7c67dc', '#38bdf8', '#34d399', '#f59e0b', '#ec4899']

  const textColor = isDark ? '#9e99ad' : '#6b7280'
  const gridColor = isDark ? '#2e284b' : '#f1f0f4'
  const tooltipBg = isDark ? '#1a172c' : '#ffffff'
  const tooltipBorder = isDark ? '#383256' : '#e5e7eb'

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px', marginTop: '20px' }}>
      {/* Weekly Meeting Volume AreaChart */}
      <div
        style={{
          background: isDark ? '#18142a' : '#ffffff',
          border: `1px solid ${isDark ? '#2b2349' : '#e8e5ec'}`,
          borderRadius: '14px',
          padding: '20px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.04)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: isDark ? '#f4f2fa' : '#1e1b33' }}>
              Weekly Meeting Time
            </h3>
            <small style={{ color: textColor }}>Total minutes spent across all calls</small>
          </div>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#6d55d8', background: isDark ? '#281f4f' : '#eeeaff', padding: '3px 8px', borderRadius: '6px' }}>
            +12% vs last week
          </span>
        </div>
        <div style={{ width: '100%', height: 180 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={weeklyActivity} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="meetoraGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#7c67dc" stopOpacity={0.6} />
                  <stop offset="95%" stopColor="#7c67dc" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="day" stroke={textColor} fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke={textColor} fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: tooltipBg,
                  borderColor: tooltipBorder,
                  borderRadius: '8px',
                  color: isDark ? '#f4f2fa' : '#111827',
                  fontSize: '12px',
                }}
                formatter={(val: any) => [`${val} min`, 'Duration']}
              />
              <Area type="monotone" dataKey="minutes" stroke="#7c67dc" strokeWidth={2.5} fillOpacity={1} fill="url(#meetoraGradient)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Speaker Participation PieChart */}
      <div
        style={{
          background: isDark ? '#18142a' : '#ffffff',
          border: `1px solid ${isDark ? '#2b2349' : '#e8e5ec'}`,
          borderRadius: '14px',
          padding: '20px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.04)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: isDark ? '#f4f2fa' : '#1e1b33' }}>
              Speaker Diarization & Participation
            </h3>
            <small style={{ color: textColor }}>Talk-time breakdown by speaker</small>
          </div>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#38bdf8', background: isDark ? '#142c40' : '#e0f2fe', padding: '3px 8px', borderRadius: '6px' }}>
            Balanced
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ width: '50%', height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={speakerData}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={70}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {speakerData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: tooltipBg,
                    borderColor: tooltipBorder,
                    borderRadius: '8px',
                    color: isDark ? '#f4f2fa' : '#111827',
                    fontSize: '12px',
                  }}
                  formatter={(val: any) => [`${val}%`, 'Talk Time']}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div style={{ width: '48%', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {speakerData.map((item, idx) => (
              <div key={item.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '8px', color: isDark ? '#ddd9ea' : '#374151' }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%', background: COLORS[idx % COLORS.length] }} />
                  {item.name}
                </span>
                <b style={{ color: isDark ? '#f4f2fa' : '#111827' }}>{item.value}%</b>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

