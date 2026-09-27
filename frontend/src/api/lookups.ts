import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { Category, Paginated, Team } from './types'

// DRF's PageNumberPagination here has a fixed PAGE_SIZE=25 (no page_size query param configured) -
// fine for teams/categories, which are a handful of seeded rows, not paginated lists in practice.
async function fetchAll<T>(url: string): Promise<T[]> {
  const { data } = await api.get<Paginated<T>>(url)
  return data.results
}

export function useCategories() {
  return useQuery({ queryKey: ['categories'], queryFn: () => fetchAll<Category>('/categories/') })
}

export function useTeams() {
  return useQuery({ queryKey: ['teams'], queryFn: () => fetchAll<Team>('/teams/') })
}
