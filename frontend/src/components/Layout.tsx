import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useMarkNotificationRead, useNotifications } from '../api/notifications'
import { useAuth } from '../api/auth'

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `rounded-md px-3 py-2 text-sm font-medium ${
          isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
        }`
      }
    >
      {label}
    </NavLink>
  )
}

function NotificationBell() {
  const [open, setOpen] = useState(false)
  const { data: notifications } = useNotifications()
  const markRead = useMarkNotificationRead()
  const navigate = useNavigate()
  const unreadCount = notifications?.filter((n) => !n.is_read).length ?? 0

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="relative rounded-md p-2 text-slate-600 hover:bg-slate-100"
        aria-label="Notifications"
      >
        🔔
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-semibold text-white">
            {unreadCount}
          </span>
        )}
      </button>
      {open && (
        <>
          <button
            type="button"
            aria-label="Close notifications"
            className="fixed inset-0 z-10 cursor-default"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 z-20 mt-2 w-80 rounded-lg border border-slate-200 bg-white shadow-lg">
            <div className="max-h-96 overflow-y-auto">
              {!notifications || notifications.length === 0 ? (
                <p className="p-4 text-sm text-slate-500">No notifications yet.</p>
              ) : (
                notifications.map((n) => (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => {
                      setOpen(false)
                      if (!n.is_read) markRead.mutate(n.id)
                      if (n.ticket) navigate(`/tickets/${n.ticket}`)
                    }}
                    className={`block w-full border-b border-slate-100 p-3 text-left text-sm last:border-0 hover:bg-slate-50 ${
                      n.is_read ? 'text-slate-500' : 'font-medium text-slate-900'
                    }`}
                  >
                    {n.message}
                  </button>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <span className="text-lg font-semibold text-slate-900">ServiceDesk Copilot</span>
            <nav className="flex items-center gap-1">
              {user?.role === 'employee' && (
                <>
                  <NavItem to="/tickets" label="My Tickets" />
                  <NavItem to="/tickets/new" label="New Ticket" />
                </>
              )}
              {(user?.role === 'agent' || user?.role === 'admin') && (
                <>
                  <NavItem to="/queue" label="Agent Queue" />
                  <NavItem to="/analytics" label="Analytics" />
                </>
              )}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <NotificationBell />
            <span className="text-sm text-slate-600">{user?.email}</span>
            <button
              type="button"
              onClick={() => {
                logout()
                navigate('/login')
              }}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
