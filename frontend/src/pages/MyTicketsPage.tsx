import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTickets } from '../api/tickets'
import { useCategories } from '../api/lookups'
import { TicketTable } from '../components/TicketTable'

export function MyTicketsPage() {
  const [page, setPage] = useState(1)
  const { data, isLoading, isError } = useTickets(page)
  const { data: categories = [] } = useCategories()

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">My Tickets</h1>
        <Link
          to="/tickets/new"
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          + New Ticket
        </Link>
      </div>

      <div className="mt-6">
        {isLoading && <p className="text-sm text-slate-500">Loading tickets…</p>}
        {isError && <p className="text-sm text-rose-600">Could not load your tickets.</p>}
        {data && <TicketTable tickets={data.results} categories={categories} showAgent />}
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
