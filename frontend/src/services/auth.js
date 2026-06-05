import { computed, reactive } from 'vue'
import { authApi } from '../api/auth'
import { ROLE_HOME_ROUTES } from '../constants/roles'
import {
  clearStoredAuth,
  getStoredToken,
  getStoredUser,
  setStoredToken,
  setStoredUser,
} from './auth-storage'

/**
 * Реактивное состояние авторизации всего frontend-приложения.
 *
 * Здесь хранится JWT, пользователь, роль и permissions. Страницы не должны
 * самостоятельно читать localStorage или декодировать токен: они используют
 * `useAuth()`, чтобы одинаково проверять доступ к разделам “Камеры”, “Гости”,
 * “План здания”, “Аналитика” и т.д.
 */
const state = reactive({
  token: getStoredToken(),
  user: getStoredUser(),
  initialized: false,
  loading: false,
})

/** Очистить runtime-состояние и сохранённые данные авторизации. */
function clearState() {
  clearStoredAuth()
  state.token = ''
  state.user = null
}

/**
 * Инициализировать сессию пользователя при открытии приложения.
 *
 * Если токен есть, frontend запрашивает `/auth/me`, чтобы получить актуальную
 * роль и permissions с backend. Это важно после изменения ролей: старые данные
 * в localStorage не должны давать пользователю лишние возможности.
 */
async function initialize(force = false) {
  if (state.loading) return state.user
  if (state.initialized && !force) return state.user

  if (!state.token) {
    state.user = null
    state.initialized = true
    return null
  }

  state.loading = true
  try {
    const response = await authApi.getMe()
    state.user = response.data
    setStoredUser(response.data)
    return state.user
  } catch {
    clearState()
    return null
  } finally {
    state.loading = false
    state.initialized = true
  }
}

/**
 * Выполнить вход по логину и паролю.
 *
 * После получения токена сразу вызывается `initialize(true)`, чтобы в состоянии
 * появился полный объект пользователя с permissions и интерфейс мог отправить
 * его на правильную стартовую страницу.
 */
async function login(username, password) {
  const response = await authApi.login(username, password)
  state.token = response.data.access_token
  setStoredToken(response.data.access_token)
  state.initialized = false
  await initialize(true)
  return state.user
}

/** Завершить сессию и при необходимости вернуть пользователя на страницу входа. */
function logout({ redirect = true } = {}) {
  clearState()
  state.initialized = true
  if (redirect && window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

/** Проверить, входит ли роль пользователя хотя бы в один из указанных вариантов. */
function hasAnyRole(...roles) {
  return Boolean(state.user && roles.includes(state.user.role))
}

/** Проверить одно конкретное permission, выданное backend-ом для роли. */
function hasPermission(permission) {
  return Boolean(state.user?.permissions?.includes(permission))
}

/** Проверить набор permissions, если достаточно хотя бы одного разрешения. */
function hasAnyPermission(...permissions) {
  return permissions.some((permission) => hasPermission(permission))
}

/** Вернуть стартовый route для роли пользователя после авторизации. */
function getDefaultRoute(role = state.user?.role) {
  return ROLE_HOME_ROUTES[role] || '/login'
}

/** Проверить, считается ли пользователь авторизованным в текущем frontend-состоянии. */
function isAuthenticated() {
  return Boolean(state.token && state.user)
}

const api = {
  state,
  initialize,
  login,
  logout,
  hasAnyRole,
  hasPermission,
  hasAnyPermission,
  getDefaultRoute,
  isAuthenticated,
  username: computed(() => state.user?.username || ''),
  role: computed(() => state.user?.role || ''),
  permissions: computed(() => state.user?.permissions || []),
}

/** Вернуть единый API авторизации для компонентов и router guard-ов. */
export function useAuth() {
  return api
}
