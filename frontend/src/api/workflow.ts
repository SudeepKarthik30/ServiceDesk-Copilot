import type { Role, TicketStatus } from './types'

// Mirrors backend/tickets/services/workflow.py ALLOWED_TRANSITIONS plus the role restrictions in
// backend/tickets/views.py (EMPLOYEE_ALLOWED_TRANSITIONS / AGENT_ALLOWED_TRANSITIONS). Kept in sync
// by hand since it only changes with the workflow itself - this is what decides which buttons to
// show; the backend is still the source of truth and will 403 anything not actually permitted.
const ALL_TRANSITIONS: Record<TicketStatus, TicketStatus[]> = {
  NEW: ['TRIAGING'],
  TRIAGING: ['AI_ANSWERED', 'ASSIGNED'],
  AI_ANSWERED: ['RESOLVED', 'ASSIGNED'],
  ASSIGNED: ['IN_PROGRESS', 'RESOLVED'],
  IN_PROGRESS: ['RESOLVED', 'ASSIGNED'],
  RESOLVED: ['CLOSED', 'REOPENED'],
  CLOSED: ['REOPENED'],
  REOPENED: ['ASSIGNED', 'IN_PROGRESS'],
}

// AI_ANSWERED's transitions are deliberately absent for employees here - those go through the
// dedicated `confirm` action (see TicketDetailPage), not the generic transition endpoint.
const EMPLOYEE_TRANSITIONS = new Set(['RESOLVED->REOPENED', 'CLOSED->REOPENED'])

const AGENT_TRANSITIONS = new Set([
  'ASSIGNED->IN_PROGRESS',
  'ASSIGNED->RESOLVED',
  'IN_PROGRESS->RESOLVED',
  'IN_PROGRESS->ASSIGNED',
  'RESOLVED->CLOSED',
  'REOPENED->ASSIGNED',
  'REOPENED->IN_PROGRESS',
])

export function availableTransitions(role: Role, status: TicketStatus): TicketStatus[] {
  const candidates = ALL_TRANSITIONS[status] ?? []
  if (role === 'admin') return candidates
  const allowed = role === 'employee' ? EMPLOYEE_TRANSITIONS : AGENT_TRANSITIONS
  return candidates.filter((to) => allowed.has(`${status}->${to}`))
}
