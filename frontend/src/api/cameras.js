import apiClient from './client'

export const camerasApi = {
  getCameras({ buildingId = null, floorId = null } = {}) {
    const params = new URLSearchParams()

    if (buildingId !== null && buildingId !== undefined && buildingId !== '') {
      params.set('building_id', String(buildingId))
    }
    if (floorId !== null && floorId !== undefined && floorId !== '') {
      params.set('floor_id', String(floorId))
    }

    const query = params.toString()
    return apiClient.get(`/cameras/${query ? `?${query}` : ''}`)
  },

  getCamera(id) {
    return apiClient.get(`/cameras/${id}`)
  },

  createCamera(payload) {
    return apiClient.post('/cameras/', payload)
  },

  updateCamera(id, payload) {
    return apiClient.patch(`/cameras/${id}`, payload)
  },

  setDemoRecognition(id, payload) {
    return apiClient.post(`/cameras/${id}/demo-recognition`, payload)
  },

  getSnapshot(id) {
    return apiClient.get(`/cameras/${id}/snapshot`, { responseType: 'blob' })
  }
}
