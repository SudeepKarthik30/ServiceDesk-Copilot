import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCreateTicket } from '../api/tickets'
import { apiErrorMessage } from '../api/client'
import type { Urgency } from '../api/types'

const URGENCY_OPTIONS: { value: Urgency; label: string }[] = [
  { value: 'P1', label: 'P1 - Critical (blocking everyone / whole team)' },
  { value: 'P2', label: 'P2 - High (blocking me)' },
  { value: 'P3', label: 'P3 - Normal' },
  { value: 'P4', label: 'P4 - Low / not urgent' },
]

export function NewTicketPage() {
  const navigate = useNavigate()
  const createTicket = useCreateTicket()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [urgency, setUrgency] = useState<Urgency>('P3')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const ticket = await createTicket.mutateAsync({ title, description, urgency })
      navigate(`/tickets/${ticket.id}`)
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not create the ticket.'))
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-xl font-semibold text-slate-900">New Ticket</h1>
      <p className="mt-1 text-sm text-slate-500">
        Describe your problem in your own words - our AI will categorize it and either solve it right away or
        route it to the right team.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4 rounded-xl bg-white p-6 shadow-sm">
        <div>
          <label htmlFor="title" className="block text-sm font-medium text-slate-700">
            Title
          </label>
          <input
            id="title"
            required
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. VPN keeps disconnecting"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          />
        </div>
        <div>
          <label htmlFor="description" className="block text-sm font-medium text-slate-700">
            Description
          </label>
          <textarea
            id="description"
            required
            rows={6}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What's happening, when did it start, what have you already tried?"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          />
        </div>
        <div>
          <label htmlFor="urgency" className="block text-sm font-medium text-slate-700">
            Urgency
          </label>
          <select
            id="urgency"
            value={urgency}
            onChange={(e) => setUrgency(e.target.value as Urgency)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          >
            {URGENCY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-slate-400">The AI may re-classify this once it reviews the ticket.</p>
        </div>
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <button
          type="submit"
          disabled={createTicket.isPending}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {createTicket.isPending ? 'Submitting…' : 'Submit Ticket'}
        </button>
      </form>
    </div>
  )
}
