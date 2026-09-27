export type Role = 'employee' | 'agent' | 'admin'

export interface UserBrief {
  id: number
  email: string
  first_name: string
  last_name: string
  role: Role
  team: number | null
}

export interface Team {
  id: number
  name: string
  created_at: string
}

export interface Category {
  id: number
  name: string
  team: number
  safe_to_auto_solve: boolean
  created_at: string
}

export type TicketStatus =
  | 'NEW'
  | 'TRIAGING'
  | 'AI_ANSWERED'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'RESOLVED'
  | 'CLOSED'
  | 'REOPENED'

export type Urgency = 'P1' | 'P2' | 'P3' | 'P4'

export interface Comment {
  id: number
  ticket: number
  author: UserBrief
  body: string
  is_internal: boolean
  created_at: string
}

export interface AIStep {
  text: string
  source: string
}

export interface AIAnswer {
  can_solve?: boolean
  confidence?: 'high' | 'medium' | 'low'
  steps?: AIStep[]
}

export interface AIResult {
  id: number
  decision: 'AUTO_ANSWER' | 'ESCALATE'
  reasons: string[]
  answer: AIAnswer
  candidates: { id: number; subject: string | null }[]
  scores: { id: number; score: number }[]
  latency_ms: number
  created_at: string
}

export interface TicketListItem {
  id: number
  title: string
  employee: UserBrief
  category: number | null
  team: number | null
  assigned_agent: UserBrief | null
  status: TicketStatus
  urgency: Urgency
  sla_due_at: string | null
  created_at: string
  updated_at: string
}

export interface TicketDetail extends TicketListItem {
  description: string
  added_to_kb: boolean
  resolved_at: string | null
  closed_at: string | null
  ai_results: AIResult[]
}

export interface Notification {
  id: number
  ticket: number | null
  message: string
  is_read: boolean
  created_at: string
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
