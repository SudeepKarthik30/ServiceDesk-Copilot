import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './api/auth'
import { Layout } from './components/Layout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AgentQueuePage } from './pages/AgentQueuePage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { LoginPage } from './pages/LoginPage'
import { MyTicketsPage } from './pages/MyTicketsPage'
import { NewTicketPage } from './pages/NewTicketPage'
import { TicketDetailPage } from './pages/TicketDetailPage'

function Home() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to={user.role === 'employee' ? '/tickets' : '/queue'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Home />} />
        <Route
          path="/tickets"
          element={
            <ProtectedRoute roles={['employee']}>
              <MyTicketsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tickets/new"
          element={
            <ProtectedRoute roles={['employee']}>
              <NewTicketPage />
            </ProtectedRoute>
          }
        />
        <Route path="/tickets/:id" element={<TicketDetailPage />} />
        <Route
          path="/queue"
          element={
            <ProtectedRoute roles={['agent', 'admin']}>
              <AgentQueuePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/analytics"
          element={
            <ProtectedRoute roles={['agent', 'admin']}>
              <AnalyticsPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
