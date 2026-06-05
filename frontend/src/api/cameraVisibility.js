import apiClient from './client'

/**
 * API зон видимости камер на плане этажа.
 *
 * Зона видимости — это 4-точечный polygon в координатах исходного изображения
 * плана. Frontend показывает такие зоны поверх SVG, а backend использует их,
 * чтобы понять, какие линии графа маршрутов попадают в область наблюдения
 * камеры.
 */
export const cameraVisibilityApi = {
  /** Получить зоны всех камер выбранного этажа. */
  getFloorZones(floorId) {
    return apiClient.get(`/floors/${floorId}/camera-visibility-zones`)
  },

  /** Получить одну зону камеры для панели редактирования камеры. */
  getCameraZone(cameraId) {
    return apiClient.get(`/cameras/${cameraId}/visibility-zone`)
  },

  /**
   * Создать или обновить зону камеры.
   *
   * `payload` содержит `floor_id` и массив `points` ровно из четырёх точек
   * `{ x, y }` в пикселях оригинального плана, а не CSS-координат экрана.
   */
  saveCameraZone(cameraId, payload) {
    return apiClient.put(`/cameras/${cameraId}/visibility-zone`, payload)
  },

  /** Удалить зону видимости камеры при сбросе настройки или удалении камеры. */
  deleteCameraZone(cameraId) {
    return apiClient.delete(`/cameras/${cameraId}/visibility-zone`)
  },
}
