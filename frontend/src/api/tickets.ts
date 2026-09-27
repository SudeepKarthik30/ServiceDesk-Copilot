import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { Comment, Paginated, TicketDetail, TicketListItem, TicketStatus, Urgency } from './types'

export function useTickets(page: number) {
  return useQuery({
    queryKey: ['tickets', page],
    queryFn: async () => {
      const { data } = await api.get<Paginated<TicketListItem>>('/tickets/', { params: { page } })
      return data
    },
  })
}

// Analytics has no dedicated aggregate endpoint yet (that's Phase 6) - walks pages of the same
// role-scoped list endpoint client-side. Bounded so a very large instance can't hang the page.
export function useAllTickets(maxPages = 20) {
  return useQuery({
    queryKey: ['tickets-all'],
    queryFn: async () => {
      const all: TicketListItem[] = []
      for (let page = 1; page <= maxPages; page++) {
        const { data } = await api.get<Paginated<TicketListItem>>('/tickets/', { params: { page } })
        all.push(...data.results)
        if (!data.next) break
      }
      return all
    },
  })
}

export function useTicket(id: number) {
  return useQuery({
    queryKey: ['ticket', id],
    queryFn: async () => {
      const { data } = await api.get<TicketDetail>(`/tickets/${id}/`)
      return data
    },
    enabled: Number.isFinite(id),
  })
}

function invalidateTicket(queryClient: ReturnType<typeof useQueryClient>, id: number) {
  queryClient.invalidateQueries({ queryKey: ['ticket', id] })
  queryClient.invalidateQueries({ queryKey: ['tickets'] })
}

export interface NewTicketInput {
  title: string
  description: string
  urgency: Urgency
}

export function useCreateTicket() {
  const queryClient = useQueryClient()
  return useMutation({
    // The create endpoint returns TicketCreateSerializer's smaller shape (id/title/description/
    // category/urgency), not the full TicketDetail - only `id` is needed to redirect afterwards.
    mutationFn: async (input: NewTicketInput) => {
      const { data } = await api.post<{ id: number }>('/tickets/', input)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tickets'] }),
  })
}

export function useConfirmTicket(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (resolved: boolean) => {
      const { data } = await api.post<TicketDetail>(`/tickets/${id}/confirm/`, { resolved })
      return data
    },
    onSuccess: () => invalidateTicket(queryClient, id),
  })
}

export function useTransitionTicket(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (status: TicketStatus) => {
      const { data } = await api.post<TicketDetail>(`/tickets/${id}/transition/`, { status })
      return data
    },
    onSuccess: () => invalidateTicket(queryClient, id),
  })
}

export function useComments(id: number) {
  return useQuery({
    queryKey: ['ticket', id, 'comments'],
    queryFn: async () => {
      const { data } = await api.get<Comment[]>(`/tickets/${id}/comments/`)
      return data
    },
    enabled: Number.isFinite(id),
  })
}

export function useAddComment(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (input: { body: string; is_internal: boolean }) => {
      const { data } = await api.post<Comment>(`/tickets/${id}/comments/`, input)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ticket', id, 'comments'] }),
  })
}

export function useAddToKb(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (input: { subject?: string; body?: string; resolution: string }) => {
      const { data } = await api.post<TicketDetail>(`/tickets/${id}/add_to_kb/`, input)
      return data
    },
    onSuccess: () => invalidateTicket(queryClient, id),
  })
}

export function useRemoveFromKb(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<TicketDetail>(`/tickets/${id}/remove_from_kb/`)
      return data
    },
    onSuccess: () => invalidateTicket(queryClient, id),
  })
}
