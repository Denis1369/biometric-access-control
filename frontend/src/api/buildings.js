import apiClient from './client'

export const buildingsApi = {
  getBuildings() {
    return apiClient.get('/buildings/')
  },

  getBuilding(id) {
    return apiClient.get(`/buildings/${id}`)
  },

  createBuilding(payload) {
    return apiClient.post('/buildings/', payload)
  },

  updateBuilding(id, payload) {
    return apiClient.patch(`/buildings/${id}`, payload)
  },

  deleteBuilding(id) {
    return apiClient.delete(`/buildings/${id}`)
  }
}
