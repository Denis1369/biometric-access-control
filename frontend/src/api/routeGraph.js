import apiClient from './client'

/**
 * API ручного графа маршрутов на плане этажа.
 *
 * Оператор ставит точки и соединяет их линиями в SVG-слое поверх плана. Этот
 * модуль сохраняет такие действия на backend: точки становятся `route_nodes`,
 * линии становятся `route_edges`, а backend затем строит кратчайшие пути по
 * этому графу.
 */
export const routeGraphApi = {
  /** Загрузить все точки и линии графа выбранного этажа. */
  getGraph(floorId) {
    return apiClient.get(`/floors/${floorId}/route-graph`)
  },

  /** Создать новую точку маршрута в координатах исходного изображения плана. */
  createNode(floorId, payload) {
    return apiClient.post(`/floors/${floorId}/route-nodes`, payload)
  },

  /** Передвинуть точку маршрута; backend пересчитает веса связанных линий. */
  updateNode(nodeId, payload) {
    return apiClient.patch(`/route-nodes/${nodeId}`, payload)
  },

  /** Удалить точку и связанные с ней линии графа. */
  deleteNode(nodeId) {
    return apiClient.delete(`/route-nodes/${nodeId}`)
  },

  /** Создать линию между двумя точками маршрута. */
  createEdge(floorId, payload) {
    return apiClient.post(`/floors/${floorId}/route-edges`, payload)
  },

  /** Удалить одну линию маршрута. */
  deleteEdge(edgeId) {
    return apiClient.delete(`/route-edges/${edgeId}`)
  },

  /** Полностью очистить ручную разметку графа на выбранном этаже. */
  clearGraph(floorId) {
    return apiClient.delete(`/floors/${floorId}/route-graph`)
  },

  /** Попросить backend построить кратчайший путь между двумя точками графа. */
  buildPath(floorId, payload) {
    return apiClient.post(`/floors/${floorId}/route-path`, payload)
  },
}
