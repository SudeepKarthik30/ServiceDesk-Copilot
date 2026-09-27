import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useAuth } from '../api/auth'
import { apiErrorMessage } from '../api/client'
import { useCategories, useTeams } from '../api/lookups'
import {
  useAddComment,
  useAddToKb,
  useComments,
  useConfirmTicket,
  useRemoveFromKb,
  useTicket,
  useTransitionTicket,
} from '../api/tickets'
import { availableTransitions } from '../api/workflow'
import { STATUS_LABELS, StatusBadge, UrgencyBadge } from '../components/StatusBadge'

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-900">{value}</dd>
    </div>
  )
}

export function TicketDetailPage() {
  const { id } = useParams()
  const ticketId = Number(id)
  const { user } = useAuth()
  const { data: ticket, isLoading, isError } = useTicket(ticketId)
  const { data: categories = [] } = useCategories()
  const { data: teams = [] } = useTeams()
  const { data: comments = [] } = useComments(ticketId)

  const confirmTicket = useConfirmTicket(ticketId)
  const transitionTicket = useTransitionTicket(ticketId)
  const addToKb = useAddToKb(ticketId)
  const removeFromKb = useRemoveFromKb(ticketId)
  const addComment = useAddComment(ticketId)

  const [actionError, setActionError] = useState<string | null>(null)
  const [showKbForm, setShowKbForm] = useState(false)
  const [kbResolution, setKbResolution] = useState('')
  const [commentBody, setCommentBody] = useState('')
  const [commentInternal, setCommentInternal] = useState(false)

  if (isLoading) return <p className="text-sm text-slate-500">Loading ticket…</p>
  if (isError || !ticket || !user) return <p className="text-sm text-rose-600">Could not load this ticket.</p>

  const isOwner = user.role === 'employee' && ticket.employee.id === user.id
  const isAssignedAgent =
    user.role === 'agent' && (ticket.assigned_agent?.id === user.id || ticket.team === user.team)
  const canAct = user.role === 'admin' || isOwner || isAssignedAgent

  const latestAiResult = ticket.ai_results[0]
  const awaitingConfirmation = ticket.status === 'AI_ANSWERED' && isOwner
  const transitions = canAct ? availableTransitions(user.role, ticket.status) : []
  const canManageKb = user.role === 'admin' || isAssignedAgent

  async function runAction(fn: () => Promise<unknown>) {
    setActionError(null)
    try {
      await fn()
    } catch (err) {
      setActionError(apiErrorMessage(err))
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold text-slate-900">
            #{ticket.id} {ticket.title}
          </h1>
          <StatusBadge status={ticket.status} />
          <UrgencyBadge urgency={ticket.urgency} />
        </div>
        <p className="mt-1 text-sm text-slate-500">Opened {formatDate(ticket.created_at)}</p>
      </div>

      {actionError && (
        <div className="rounded-md bg-rose-50 px-4 py-2 text-sm text-rose-700">{actionError}</div>
      )}

      <div className="rounded-xl bg-white p-6 shadow-sm">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field label="Employee" value={ticket.employee.email} />
          <Field label="Category" value={categories.find((c) => c.id === ticket.category)?.name ?? '—'} />
          <Field label="Team" value={teams.find((t) => t.id === ticket.team)?.name ?? '—'} />
          <Field label="Assigned agent" value={ticket.assigned_agent?.email ?? '—'} />
          <Field label="SLA due" value={formatDate(ticket.sla_due_at)} />
          <Field label="In KB" value={ticket.added_to_kb ? 'Yes' : 'No'} />
        </dl>
        <div className="mt-4 border-t border-slate-100 pt-4">
          <h2 className="text-xs font-medium uppercase tracking-wide text-slate-400">Description</h2>
          <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">{ticket.description}</p>
        </div>
      </div>

      {latestAiResult && (
        <div className="rounded-xl border border-violet-200 bg-violet-50 p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-violet-900">AI Assessment</h2>
            <span className="text-xs text-violet-600">{latestAiResult.decision.replace('_', ' ')}</span>
          </div>
          {latestAiResult.reasons.length > 0 && (
            <p className="mt-1 text-xs text-violet-600">{latestAiResult.reasons.join(', ')}</p>
          )}
          {latestAiResult.answer.steps && latestAiResult.answer.steps.length > 0 ? (
            <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm text-slate-800">
              {latestAiResult.answer.steps.map((step, i) => (
                <li key={i}>
                  {step.text}{' '}
                  <span className="text-xs text-slate-400">(source #{step.source})</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-3 text-sm text-slate-600">
              The AI could not find a confident, grounded fix and escalated this ticket to an agent.
            </p>
          )}

          {awaitingConfirmation && (
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                disabled={confirmTicket.isPending}
                onClick={() => runAction(() => confirmTicket.mutateAsync(true))}
                className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                ✅ Fixed
              </button>
              <button
                type="button"
                disabled={confirmTicket.isPending}
                onClick={() => runAction(() => confirmTicket.mutateAsync(false))}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
              >
                ❌ Didn't work
              </button>
            </div>
          )}
        </div>
      )}

      {transitions.length > 0 && (
        <div className="rounded-xl bg-white p-6 shadow-sm">
          <h2 className="text-xs font-medium uppercase tracking-wide text-slate-400">Actions</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {transitions.map((status) => (
              <button
                key={status}
                type="button"
                disabled={transitionTicket.isPending}
                onClick={() => runAction(() => transitionTicket.mutateAsync(status))}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
              >
                Mark as {STATUS_LABELS[status]}
              </button>
            ))}
          </div>
        </div>
      )}

      {canManageKb && ticket.status === 'RESOLVED' && (
        <div className="rounded-xl bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-medium uppercase tracking-wide text-slate-400">Knowledge Base</h2>
            {ticket.added_to_kb ? (
              <button
                type="button"
                disabled={removeFromKb.isPending}
                onClick={() => runAction(() => removeFromKb.mutateAsync())}
                className="text-sm text-rose-600 hover:underline disabled:opacity-50"
              >
                Remove from KB
              </button>
            ) : (
              !showKbForm && (
                <button
                  type="button"
                  onClick={() => setShowKbForm(true)}
                  className="text-sm text-slate-700 hover:underline"
                >
                  + Add to KB
                </button>
              )
            )}
          </div>
          {!ticket.added_to_kb && showKbForm && (
            <div className="mt-3 space-y-2">
              <textarea
                rows={4}
                value={kbResolution}
                onChange={(e) => setKbResolution(e.target.value)}
                placeholder="Write the actual, actionable fix for this problem (this is what gets searched for future tickets)."
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={addToKb.isPending || !kbResolution.trim()}
                  onClick={() =>
                    runAction(async () => {
                      await addToKb.mutateAsync({ resolution: kbResolution })
                      setShowKbForm(false)
                      setKbResolution('')
                    })
                  }
                  className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                >
                  Save to KB
                </button>
                <button
                  type="button"
                  onClick={() => setShowKbForm(false)}
                  className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="rounded-xl bg-white p-6 shadow-sm">
        <h2 className="text-xs font-medium uppercase tracking-wide text-slate-400">Comments</h2>
        <div className="mt-3 space-y-3">
          {comments.length === 0 && <p className="text-sm text-slate-400">No comments yet.</p>}
          {comments.map((comment) => (
            <div key={comment.id} className="rounded-md border border-slate-100 p-3">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-medium text-slate-600">{comment.author.email}</span>
                <span>{formatDate(comment.created_at)}</span>
              </div>
              {comment.is_internal && (
                <span className="mt-1 inline-block rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800">
                  Internal note
                </span>
              )}
              <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">{comment.body}</p>
            </div>
          ))}
        </div>

        {canAct && (
          <div className="mt-4 space-y-2 border-t border-slate-100 pt-4">
            <textarea
              rows={3}
              value={commentBody}
              onChange={(e) => setCommentBody(e.target.value)}
              placeholder="Add a comment…"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
            />
            <div className="flex items-center justify-between">
              {user.role !== 'employee' ? (
                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input
                    type="checkbox"
                    checked={commentInternal}
                    onChange={(e) => setCommentInternal(e.target.checked)}
                    className="rounded border-slate-300"
                  />
                  Internal note (hidden from employee)
                </label>
              ) : (
                <span />
              )}
              <button
                type="button"
                disabled={addComment.isPending || !commentBody.trim()}
                onClick={() =>
                  runAction(async () => {
                    await addComment.mutateAsync({ body: commentBody, is_internal: commentInternal })
                    setCommentBody('')
                    setCommentInternal(false)
                  })
                }
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                Post Comment
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
