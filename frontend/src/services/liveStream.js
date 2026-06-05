/**
 * Получает 2D-контекст canvas с настройками для частого обновления кадров.
 *
 * `desynchronized` просит браузер уменьшить задержку отрисовки, что полезно
 * для live-потока камеры. Если браузер не поддерживает опцию, он просто
 * проигнорирует её.
 */
function getCanvasContext(canvas) {
  return canvas.getContext('2d', { alpha: false, desynchronized: true })
}

/**
 * Подгоняет внутреннее разрешение canvas под текущий размер элемента.
 *
 * CSS-размер canvas и его bitmap-размер могут отличаться. Если не синхронизировать
 * их, изображение камеры будет мыльным или растянутым. Функция возвращает
 * актуальный размер области рисования.
 */
function fitCanvasToElement(canvas, sourceWidth, sourceHeight) {
  const width = Math.max(1, Math.round(canvas.clientWidth || sourceWidth || 1))
  const height = Math.max(1, Math.round(canvas.clientHeight || sourceHeight || 1))

  if (canvas.width !== width) {
    canvas.width = width
  }
  if (canvas.height !== height) {
    canvas.height = height
  }

  return { width, height }
}

/**
 * Нарисовать кадр по центру canvas с сохранением пропорций.
 *
 * Кадры камер могут иметь разное соотношение сторон, а карточка просмотра в UI
 * может быть шире или уже. Поэтому используется `object-fit: contain` в ручном
 * виде: чёрный фон и масштабирование без обрезания кадра.
 */
function drawToCanvas(canvas, source) {
  const ctx = getCanvasContext(canvas)
  if (!ctx) return

  const sourceWidth = source.width || source.videoWidth || canvas.width || 1
  const sourceHeight = source.height || source.videoHeight || canvas.height || 1
  const { width, height } = fitCanvasToElement(canvas, sourceWidth, sourceHeight)

  ctx.fillStyle = '#000'
  ctx.fillRect(0, 0, width, height)

  const scale = Math.min(width / sourceWidth, height / sourceHeight)
  const drawWidth = sourceWidth * scale
  const drawHeight = sourceHeight * scale
  const offsetX = (width - drawWidth) / 2
  const offsetY = (height - drawHeight) / 2

  ctx.drawImage(source, offsetX, offsetY, drawWidth, drawHeight)
}

/** Очистить canvas при закрытии потока или уходе со страницы. */
function clearCanvas(canvas) {
  const ctx = getCanvasContext(canvas)
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)
}

/**
 * Декодировать JPEG-пакет из WebSocket в объект, который можно нарисовать.
 *
 * В современных браузерах используется `createImageBitmap`, потому что он
 * быстрее и умеет освобождать ресурсы через `close()`. Для fallback создаётся
 * обычный `Image` через object URL.
 */
async function decodeFrame(payload) {
  const blob = payload instanceof Blob ? payload : new Blob([payload], { type: 'image/jpeg' })

  if ('createImageBitmap' in window) {
    return createImageBitmap(blob)
  }

  return await new Promise((resolve, reject) => {
    const img = new Image()
    const objectUrl = URL.createObjectURL(blob)

    img.onload = () => {
      URL.revokeObjectURL(objectUrl)
      resolve(img)
    }
    img.onerror = (error) => {
      URL.revokeObjectURL(objectUrl)
      reject(error)
    }
    img.src = objectUrl
  })
}

/** Освободить декодированный кадр, если браузер поддерживает `ImageBitmap.close`. */
function closeDecodedFrame(frame) {
  if (frame && typeof frame.close === 'function') {
    frame.close()
  }
}

/**
 * Создать player live-потока камеры на базе WebSocket и canvas.
 *
 * Backend отправляет бинарные JPEG-кадры. Player хранит только последний
 * полученный payload: если декодирование не успевает за потоком, старые кадры
 * выбрасываются. Для видеонаблюдения это правильнее, чем копить очередь и
 * показывать оператору картинку с задержкой.
 */
export function createCanvasStreamPlayer({
  url,
  canvas,
  onOpen,
  onFirstFrame,
  onFrame,
  onError,
  onClose,
}) {
  if (!canvas) {
    throw new Error('Canvas element is required for live stream player')
  }

  const socket = new WebSocket(url)
  socket.binaryType = 'blob'

  let isClosed = false
  let isRendering = false
  let latestPayload = null
  let hasFirstFrame = false

  const renderLoop = async () => {
    if (isClosed || isRendering) return
    isRendering = true

    try {
      while (latestPayload && !isClosed) {
        const payload = latestPayload
        latestPayload = null

        const decodedFrame = await decodeFrame(payload)
        try {
          if (isClosed) {
            break
          }

          drawToCanvas(canvas, decodedFrame)

          if (!hasFirstFrame) {
            hasFirstFrame = true
            onFirstFrame?.()
          }
          onFrame?.()
        } finally {
          closeDecodedFrame(decodedFrame)
        }
      }
    } catch (error) {
      onError?.(error)
    } finally {
      isRendering = false
      if (latestPayload && !isClosed) {
        void renderLoop()
      }
    }
  }

  socket.onopen = () => {
    if (isClosed) return
    onOpen?.()
  }

  socket.onmessage = (event) => {
    if (isClosed) return
    latestPayload = event.data
    void renderLoop()
  }

  socket.onerror = (error) => {
    if (isClosed) return
    onError?.(error)
  }

  socket.onclose = (event) => {
    if (isClosed) return
    onClose?.(event)
  }

  return {
    close(code = 1000, reason = 'client_closed') {
      if (isClosed) return
      isClosed = true
      latestPayload = null
      socket.onopen = null
      socket.onmessage = null
      socket.onerror = null
      socket.onclose = null
      if (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN) {
        socket.close(code, reason)
      }
      clearCanvas(canvas)
    },
  }
}
