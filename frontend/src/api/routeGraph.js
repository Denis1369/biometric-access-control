import apiClient from './client'

export const routeGraphApi = {
  getGraph(floorId) {
    return apiClient.get(`/floors/${floorId}/route-graph`)
  },

  createNode(floorId, payload) {
    return apiClient.post(`/floors/${floorId}/route-nodes`, payload)
  },

  updateNode(nodeId, payload) {
    return apiClient.patch(`/route-nodes/${nodeId}`, payload)
  },

  deleteNode(nodeId) {
    return apiClient.delete(`/route-nodes/${nodeId}`)
  },

  createEdge(floorId, payload) {
    return apiClient.post(`/floors/${floorId}/route-edges`, payload)
  },

  deleteEdge(edgeId) {
    return apiClient.delete(`/route-edges/${edgeId}`)
  },

  clearGraph(floorId) {
    return apiClient.delete(`/floors/${floorId}/route-graph`)
  },

  buildPath(floorId, payload) {
    return apiClient.post(`/floors/${floorId}/route-path`, payload)
  },
}
