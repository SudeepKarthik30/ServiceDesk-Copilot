import type { TicketStatus, Urgency } from '../api/types'

const STATUS_STYLES: Record<TicketStatus, string> = {
  NEW: 'bg-slate-100 text-slate-700',
  TRIAGING: 'bg-amber-100 text-amber-800',
  AI_ANSWERED: 'bg-violet-100 text-violet-800',
  ASSIGNED: 'bg-blue-100 text-blue-800',
  IN_PROGRESS: 'bg-sky-100 text-sky-800',
  RESOLVED: 'bg-emerald-100 text-emerald-800',
  CLOSED: 'bg-slate-200 text-slate-600',
  REOPENED: 'bg-rose-100 text-rose-800',
}

export const STATUS_LABELS: Record<TicketStatus, string> = {
  NEW: 'New',
  TRIAGING: 'Triaging',
  AI_ANSWERED: 'AI Answered',
  ASSIGNED: 'Assigned',
  IN_PROGRESS: 'In Progress',
  RESOLVED: 'Resolved',
  CLOSED: 'Closed',
  REOPENED: 'Reopened',
}

export function StatusBadge({ status }: { status: TicketStatus }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  )
}

const URGENCY_STYLES: Record<Urgency, string> = {
  P1: 'bg-red-100 text-red-800',
  P2: 'bg-orange-100 text-orange-800',
  P3: 'bg-slate-100 text-slate-700',
  P4: 'bg-slate-100 text-slate-500',
}

export function UrgencyBadge({ urgency }: { urgency: Urgency }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${URGENCY_STYLES[urgency]}`}>
      {urgency}
    </span>
  )
}
