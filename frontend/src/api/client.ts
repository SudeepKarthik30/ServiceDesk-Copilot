import axios from 'axios'

const ACCESS_KEY = 'sdc_access'
const REFRESH_KEY = 'sdc_refresh'

export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  },
  setAccess(access: string) {
    localStorage.setItem(ACCESS_KEY, access)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// A ref cell rather than a plain variable so concurrent 401s share one in-flight refresh call.
let refreshInFlight: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStore.getRefresh()
  if (!refresh) return null
  try {
    const { data } = await axios.post<{ access: string }>('/api/auth/token/refresh/', { refresh })
    tokenStore.setAccess(data.access)
    return data.access
  } catch {
    tokenStore.clear()
    return null
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const isAuthRoute = original?.url?.includes('/auth/token')
    if (error.response?.status === 401 && !original._retry && !isAuthRoute && tokenStore.getRefresh()) {
      original._retry = true
      refreshInFlight ??= refreshAccessToken()
      const newAccess = await refreshInFlight
      refreshInFlight = null
      if (newAccess) {
        original.headers.Authorization = `Bearer ${newAccess}`
        return api(original)
      }
      window.location.assign('/login')
    }
    return Promise.reject(error)
  },
)

export function apiErrorMessage(error: unknown, fallback = 'Something went wrong.'): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return detail
  }
  return fallback
}
