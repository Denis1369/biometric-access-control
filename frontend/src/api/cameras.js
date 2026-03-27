import apiClient from './client'

export const camerasApi = {
  getCameras(skip = 0, limit = 100) {
    return apiClient.get(`/cameras/?skip=${skip}&limit=${limit}`)
  },

  createCamera(data) {
    return apiClient.post('/cameras/', data)
  },

  updateCamera(id, data) {
    return apiClient.patch(`/cameras/${id}`, data)
  },

  deleteCamera(id) {
    return apiClient.delete(`/cameras/${id}`)
  }
}