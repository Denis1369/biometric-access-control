import apiClient from './client'

/**
 * Преобразует объект фильтров в query string для endpoint-ов маршрута гостя.
 *
 * Пустые значения не отправляются, чтобы backend отличал “фильтр не задан” от
 * реально выбранной даты или времени. Это особенно важно для периода построения
 * маршрута: если время не указано, backend берёт все доступные события гостя.
 */
function buildQuery(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  })
  const query = search.toString()
  return query ? `?${query}` : ''
}

/**
 * API вероятного маршрута гостя.
 *
 * Эти методы используются модальным окном гостя и страницей Tracking. Они не
 * рисуют маршрут сами, а только получают от backend события камер, зоны
 * видимости, точки/линии графа и статус offline job анализа видео.
 */
export const guestRoutesApi = {
  /**
   * Получить отладочную информацию: какие участки графа пересекаются зонами камер этажа.
   */
  getCameraRouteCandidates(floorId) {
    return apiClient.get(`/floors/${floorId}/camera-route-candidates`)
  },

  /**
   * Построить маршрут по уже записанному журналу TrackingLog/AccessLog.
   *
   * `params` обычно содержит `time_from` и `time_to`. Это быстрый сценарий:
   * backend не анализирует видео заново, а берёт уже существующие события гостя.
   */
  getGuestProbableRoute(floorId, guestId, params = {}) {
    return apiClient.get(`/floors/${floorId}/guests/${guestId}/probable-route${buildQuery(params)}`)
  },

  /**
   * Запустить тяжёлый offline-анализ file-видео камер выбранного этажа.
   *
   * Backend создаёт job, в фоне ищет выбранного гостя по Re-ID, пишет события в
   * TrackingLog и отдаёт прогресс через WebSocket.
   */
  createGuestRouteAnalysisJob(floorId, guestId) {
    return apiClient.post(`/floors/${floorId}/guests/${guestId}/route-analysis-jobs`)
  },

  /**
   * Получить текущее состояние offline job и готовый маршрут после завершения.
   */
  getGuestRouteAnalysisJob(jobId) {
    return apiClient.get(`/guest-route-analysis-jobs/${jobId}`)
  },
}
