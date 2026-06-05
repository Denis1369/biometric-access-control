const TOKEN_KEY = 'skud_access_token'
const USER_KEY = 'skud_current_user'

/**
 * Безопасно получить `localStorage`.
 *
 * В обычном Vite-приложении код выполняется в браузере, но такая проверка
 * защищает сервис от ошибок в тестах, SSR-подобных сценариях или при раннем
 * импорте модуля, когда `window` ещё недоступен.
 */
function getStorage() {
  if (typeof window === 'undefined' || !window.localStorage) {
    return null
  }
  return window.localStorage
}

/** Получить сохранённый JWT-токен текущего пользователя. */
export function getStoredToken() {
  return getStorage()?.getItem(TOKEN_KEY) || ''
}

/**
 * Сохранить или удалить JWT-токен.
 *
 * Пустое значение трактуется как logout/сброс авторизации. Остальной frontend
 * не работает напрямую с ключами localStorage, чтобы формат хранения можно было
 * поменять в одном месте.
 */
export function setStoredToken(token) {
  const storage = getStorage()
  if (!storage) return
  if (!token) {
    storage.removeItem(TOKEN_KEY)
    return
  }
  storage.setItem(TOKEN_KEY, token)
}

/**
 * Получить сохранённые данные пользователя.
 *
 * Помимо токена интерфейсу нужны роль, permissions и имя пользователя. Если
 * JSON повреждён, сервис возвращает `null`, а `auth.js` заново проверит сессию
 * через backend или отправит пользователя на login.
 */
export function getStoredUser() {
  const raw = getStorage()?.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

/** Сохранить или удалить объект текущего пользователя. */
export function setStoredUser(user) {
  const storage = getStorage()
  if (!storage) return
  if (!user) {
    storage.removeItem(USER_KEY)
    return
  }
  storage.setItem(USER_KEY, JSON.stringify(user))
}

/** Полностью очистить локальные данные авторизации. */
export function clearStoredAuth() {
  const storage = getStorage()
  if (!storage) return
  storage.removeItem(TOKEN_KEY)
  storage.removeItem(USER_KEY)
}
