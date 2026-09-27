import { Link } from 'react-router-dom'
import type { Category, TicketListItem } from '../api/types'
import { StatusBadge, UrgencyBadge } from './StatusBadge'

function formatDate(value: string) {
  return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function TicketTable({
  tickets,
  categories,
  showEmployee = false,
  showAgent = false,
}: {
  tickets: TicketListItem[]
  categories: Category[]
  showEmployee?: boolean
  showAgent?: boolean
}) {
  const categoryName = (id: number | null) => categories.find((c) => c.id === id)?.name ?? '—'

  if (tickets.length === 0) {
    return <p className="rounded-xl bg-white p-8 text-center text-sm text-slate-500 shadow-sm">No tickets here.</p>
  }

  return (
    <div className="overflow-hidden rounded-xl bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Ticket</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Urgency</th>
            <th className="px-4 py-3">Category</th>
            {showEmployee && <th className="px-4 py-3">Employee</th>}
            {showAgent && <th className="px-4 py-3">Agent</th>}
            <th className="px-4 py-3">Created</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tickets.map((ticket) => (
            <tr key={ticket.id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <Link to={`/tickets/${ticket.id}`} className="font-medium text-slate-900 hover:underline">
                  #{ticket.id} {ticket.title}
                </Link>
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={ticket.status} />
              </td>
              <td className="px-4 py-3">
                <UrgencyBadge urgency={ticket.urgency} />
              </td>
              <td className="px-4 py-3 text-slate-600">{categoryName(ticket.category)}</td>
              {showEmployee && <td className="px-4 py-3 text-slate-600">{ticket.employee.email}</td>}
              {showAgent && (
                <td className="px-4 py-3 text-slate-600">{ticket.assigned_agent?.email ?? '—'}</td>
              )}
              <td className="px-4 py-3 whitespace-nowrap text-slate-500">{formatDate(ticket.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
