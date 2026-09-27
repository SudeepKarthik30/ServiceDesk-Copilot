import { useState } from 'react'
import { useTickets } from '../api/tickets'
import { useCategories } from '../api/lookups'
import { TicketTable } from '../components/TicketTable'

const CLOSED_STATUSES = new Set(['RESOLVED', 'CLOSED'])

export function AgentQueuePage() {
  const [page, setPage] = useState(1)
  const [showClosed, setShowClosed] = useState(false)
  const { data, isLoading, isError } = useTickets(page)
  const { data: categories = [] } = useCategories()

  const visible = data?.results.filter((t) => showClosed || !CLOSED_STATUSES.has(t.status)) ?? []

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Agent Queue</h1>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={showClosed}
            onChange={(e) => setShowClosed(e.target.checked)}
            className="rounded border-slate-300"
          />
          Show resolved/closed
        </label>
      </div>

      <div className="mt-6">
        {isLoading && <p className="text-sm text-slate-500">Loading tickets…</p>}
        {isError && <p className="text-sm text-rose-600">Could not load the queue.</p>}
        {data && <TicketTable tickets={visible} categories={categories} showEmployee showAgent />}
      </div>

      {data && (data.next || data.previous) && (
        <div className="mt-4 flex items-center justify-between text-sm">
          <button
            type="button"
            disabled={!data.previous}
            onClick={() => setPage((p) => p - 1)}
            className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-slate-500">{data.count} total</span>
          <button
            type="button"
            disabled={!data.next}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
