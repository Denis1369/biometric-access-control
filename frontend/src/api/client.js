import axios from 'axios'
import { clearStoredAuth, getStoredToken } from '../services/auth-storage'

function resolveApiBaseUrl() {
  const configured = String(import.meta.env.VITE_API_BASE_URL || '').trim()
  if (!configured) {
    return 'http://localhost:8000/api'
  }

  try {
    return new URL(configured, window.location.origin).toString().replace(/\/$/, '')
  } catch {
    return 'http://localhost:8000/api'
  }
}

const apiClient = axios.create({
  baseURL: resolveApiBaseUrl(),
  headers: {
    'Content-Type': 'application/json'
  }
})

apiClient.interceptors.request.use((config) => {
  const token = getStoredToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      clearStoredAuth()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export function buildApiUrl(path, { withToken = false } = {}) {
  const normalizedBase = String(apiClient.defaults.baseURL || '').replace(/\/$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const url = new URL(`${normalizedBase}${normalizedPath}`)

  if (withToken) {
    const token = getStoredToken()
    if (token) {
      url.searchParams.set('token', token)
    }
  }

  return url.toString()
}

export function buildWsUrl(path) {
  const apiBase = new URL(String(apiClient.defaults.baseURL || 'http://localhost:8000/api'))
  const protocol = apiBase.protocol === 'https:' ? 'wss:' : 'ws:'
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const url = new URL(`${protocol}//${apiBase.host}${normalizedPath}`)
  const token = getStoredToken()
  if (token) {
    url.searchParams.set('token', token)
  }
  return url.toString()
}

export default apiClient
