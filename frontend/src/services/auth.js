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

const state = reactive({
  token: getStoredToken(),
  user: getStoredUser(),
  initialized: false,
  loading: false,
})

function clearState() {
  clearStoredAuth()
  state.token = ''
  state.user = null
}

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

async function login(username, password) {
  const response = await authApi.login(username, password)
  state.token = response.data.access_token
  setStoredToken(response.data.access_token)
  state.initialized = false
  await initialize(true)
  return state.user
}

function logout({ redirect = true } = {}) {
  clearState()
  state.initialized = true
  if (redirect && window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

function hasAnyRole(...roles) {
  return Boolean(state.user && roles.includes(state.user.role))
}

function getDefaultRoute(role = state.user?.role) {
  return ROLE_HOME_ROUTES[role] || '/login'
}

function isAuthenticated() {
  return Boolean(state.token && state.user)
}

const api = {
  state,
  initialize,
  login,
  logout,
  hasAnyRole,
  getDefaultRoute,
  isAuthenticated,
  username: computed(() => state.user?.username || ''),
  role: computed(() => state.user?.role || ''),
}

export function useAuth() {
  return api
}
