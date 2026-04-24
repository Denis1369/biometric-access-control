const TOKEN_KEY = 'skud_access_token'
const USER_KEY = 'skud_current_user'

function getStorage() {
  if (typeof window === 'undefined' || !window.localStorage) {
    return null
  }
  return window.localStorage
}

export function getStoredToken() {
  return getStorage()?.getItem(TOKEN_KEY) || ''
}

export function setStoredToken(token) {
  const storage = getStorage()
  if (!storage) return
  if (!token) {
    storage.removeItem(TOKEN_KEY)
    return
  }
  storage.setItem(TOKEN_KEY, token)
}

export function getStoredUser() {
  const raw = getStorage()?.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function setStoredUser(user) {
  const storage = getStorage()
  if (!storage) return
  if (!user) {
    storage.removeItem(USER_KEY)
    return
  }
  storage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearStoredAuth() {
  const storage = getStorage()
  if (!storage) return
  storage.removeItem(TOKEN_KEY)
  storage.removeItem(USER_KEY)
}
