import axios from 'axios'
import { clearStoredAuth, getStoredToken } from '../services/auth-storage'

/**
 * Определяет базовый адрес backend API.
 *
 * В разработке приложение обычно работает на Vite-порту, а backend на
 * `localhost:8000`, поэтому при отсутствии `VITE_API_BASE_URL` используется
 * стандартный адрес FastAPI. Если переменная окружения задана, она нормализуется
 * относительно текущего origin и без завершающего слэша, чтобы остальные
 * API-модули могли безопасно писать пути вида `/guests/`.
 */
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

/**
 * Перед каждым HTTP-запросом добавляет JWT-токен в `Authorization`.
 *
 * Токен хранится в browser storage через `auth-storage`. Компоненты и страницы
 * не должны вручную подставлять заголовок: это централизовано здесь, чтобы
 * авторизация одинаково работала для сотрудников, гостей, камер, планов и
 * аналитики.
 */
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

/**
 * Собирает полный HTTP URL к backend endpoint-у.
 *
 * Функция нужна для ссылок, которые браузер открывает напрямую: изображения
 * планов этажей, фотографии гостей, preview-кадры анализа видео. Для таких
 * ресурсов нельзя положиться на axios interceptor, поэтому при `withToken`
 * JWT добавляется в query-параметр `token`.
 */
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

/**
 * Собирает WebSocket URL к backend endpoint-у и добавляет JWT в query.
 *
 * WebSocket не использует обычные axios-заголовки, поэтому токен передаётся в
 * URL. Backend затем проверяет его так же, как HTTP-запросы, и решает, можно ли
 * пользователю подписаться на поток камеры, прогресс анализа или журнал событий.
 */
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
