import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useCategories } from '../api/lookups'
import { useAllTickets } from '../api/tickets'
import { STATUS_LABELS } from '../components/StatusBadge'
import type { TicketStatus, Urgency } from '../api/types'

// Validated categorical palette (dataviz skill, references/palette.md) - fixed order, one hue per
// status so each bar's color is stable across renders/filters, not reassigned by rank.
const STATUS_ORDER: TicketStatus[] = [
  'NEW',
  'TRIAGING',
  'AI_ANSWERED',
  'ASSIGNED',
  'IN_PROGRESS',
  'RESOLVED',
  'CLOSED',
  'REOPENED',
]
const CATEGORICAL_8 = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948']

// P1 (most severe) -> darkest step of the sequential blue ramp; P4 -> lightest. An ordered
// severity scale is an ordinal encoding, not four unrelated categories.
const URGENCY_ORDER: Urgency[] = ['P1', 'P2', 'P3', 'P4']
const URGENCY_RAMP = ['#0d366b', '#1c5cab', '#3987e5', '#86b6ef']

const SEQUENTIAL_BLUE = '#2a78d6'
const INK_SECONDARY = '#52514e'
const GRIDLINE = '#e1e0d9'

const OPEN_STATUSES = new Set<TicketStatus>(['NEW', 'TRIAGING', 'AI_ANSWERED', 'ASSIGNED', 'IN_PROGRESS', 'REOPENED'])

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl bg-white p-5 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-3xl font-semibold text-slate-900">{value}</p>
    </div>
  )
}

export function AnalyticsPage() {
  const { data: tickets, isLoading, isError } = useAllTickets()
  const { data: categories = [] } = useCategories()

  const stats = useMemo(() => {
    if (!tickets) return null

    const byStatus = STATUS_ORDER.map((status) => ({
      status,
      label: STATUS_LABELS[status],
      count: tickets.filter((t) => t.status === status).length,
    }))

    const byCategory = categories
      .map((c) => ({ name: c.name, count: tickets.filter((t) => t.category === c.id).length }))
      .filter((row) => row.count > 0)
      .sort((a, b) => b.count - a.count)

    const byUrgency = URGENCY_ORDER.map((urgency) => ({
      urgency,
      count: tickets.filter((t) => t.urgency === urgency).length,
    }))

    const open = tickets.filter((t) => OPEN_STATUSES.has(t.status)).length
    const resolved = tickets.filter((t) => t.status === 'RESOLVED' || t.status === 'CLOSED').length
    const autoAnswered = tickets.filter((t) => t.status === 'AI_ANSWERED').length

    return { byStatus, byCategory, byUrgency, total: tickets.length, open, resolved, autoAnswered }
  }, [tickets, categories])

  if (isLoading) return <p className="text-sm text-slate-500">Loading analytics…</p>
  if (isError || !stats) return <p className="text-sm text-rose-600">Could not load analytics.</p>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Analytics</h1>
        <p className="mt-1 text-sm text-slate-500">
          Computed from the {stats.total} tickets visible to you. Seeded demo volume and SQL-level
          aggregates land in Phase 6.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="Total tickets" value={stats.total} />
        <StatTile label="Open" value={stats.open} />
        <StatTile label="Resolved" value={stats.resolved} />
        <StatTile label="Currently AI-answered" value={stats.autoAnswered} />
      </div>

      <div className="rounded-xl bg-white p-6 shadow-sm">
        <h2 className="text-sm font-medium text-slate-700">Tickets by status</h2>
        <div className="mt-4 h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={stats.byStatus} margin={{ top: 16, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={GRIDLINE} />
              <XAxis dataKey="label" tick={{ fill: INK_SECONDARY, fontSize: 12 }} axisLine={{ stroke: GRIDLINE }} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fill: INK_SECONDARY, fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: '#f9f9f7' }} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={56}>
                <LabelList dataKey="count" position="top" style={{ fill: INK_SECONDARY, fontSize: 12 }} />
                {stats.byStatus.map((row) => (
                  <Cell key={row.status} fill={CATEGORICAL_8[STATUS_ORDER.indexOf(row.status)]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <div className="rounded-xl bg-white p-6 shadow-sm">
          <h2 className="text-sm font-medium text-slate-700">Tickets by category</h2>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart layout="vertical" data={stats.byCategory} margin={{ top: 0, right: 24, left: 8, bottom: 0 }}>
                <CartesianGrid horizontal={false} stroke={GRIDLINE} />
                <XAxis type="number" allowDecimals={false} tick={{ fill: INK_SECONDARY, fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={120}
                  tick={{ fill: INK_SECONDARY, fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip cursor={{ fill: '#f9f9f7' }} />
                <Bar dataKey="count" fill={SEQUENTIAL_BLUE} radius={[0, 4, 4, 0]} maxBarSize={20}>
                  <LabelList dataKey="count" position="right" style={{ fill: INK_SECONDARY, fontSize: 12 }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl bg-white p-6 shadow-sm">
          <h2 className="text-sm font-medium text-slate-700">Tickets by urgency</h2>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.byUrgency} margin={{ top: 16, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={GRIDLINE} />
                <XAxis dataKey="urgency" tick={{ fill: INK_SECONDARY, fontSize: 12 }} axisLine={{ stroke: GRIDLINE }} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fill: INK_SECONDARY, fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: '#f9f9f7' }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={56}>
                  <LabelList dataKey="count" position="top" style={{ fill: INK_SECONDARY, fontSize: 12 }} />
                  {stats.byUrgency.map((row) => (
                    <Cell key={row.urgency} fill={URGENCY_RAMP[URGENCY_ORDER.indexOf(row.urgency)]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}
