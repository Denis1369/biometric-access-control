import apiClient from './client'

export const cameraVisibilityApi = {
  getFloorZones(floorId) {
    return apiClient.get(`/floors/${floorId}/camera-visibility-zones`)
  },

  getCameraZone(cameraId) {
    return apiClient.get(`/cameras/${cameraId}/visibility-zone`)
  },

  saveCameraZone(cameraId, payload) {
    return apiClient.put(`/cameras/${cameraId}/visibility-zone`, payload)
  },

  deleteCameraZone(cameraId) {
    return apiClient.delete(`/cameras/${cameraId}/visibility-zone`)
  },
}
