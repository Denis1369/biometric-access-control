import { buildWsUrl } from '../api/client'

/**
 * Создаёт WebSocket-подключение, которое ожидает JSON-сообщения от backend.
 *
 * Такой формат используется для прогресса фоновых задач, новых событий журнала
 * и других небольших структурированных сообщений. Функция сама собирает URL с
 * JWT-токеном через `buildWsUrl`, парсит `event.data` как JSON и отдаёт
 * компоненту уже готовый объект.
 *
 * При `close()` callbacks отключаются до закрытия сокета. Это важно для Vue:
 * если компонент размонтировался сам, он не должен получить `onClose` или
 * `onError` и попытаться обновить уже уничтоженное состояние.
 */
export function createJsonWebSocket({ path, onMessage, onError, onClose }) {
  const socket = new WebSocket(buildWsUrl(path))
  let closedByClient = false

  socket.onmessage = (event) => {
    try {
      onMessage?.(JSON.parse(event.data))
    } catch (error) {
      onError?.(error)
    }
  }

  socket.onerror = (event) => {
    if (!closedByClient) onError?.(event)
  }

  socket.onclose = (event) => {
    if (!closedByClient) onClose?.(event)
  }

  return {
    close(code = 1000, reason = 'client_closed') {
      closedByClient = true
      socket.onmessage = null
      socket.onerror = null
      socket.onclose = null
      if (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN) {
        socket.close(code, reason)
      }
    },
  }
}
