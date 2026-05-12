import { buildWsUrl } from '../api/client'

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
