import apiClient from './client'

function normalizeBaseUrl(url) {
  if (!url) return ''
  return url.endsWith('/') ? url.slice(0, -1) : url
}

export const floorsApi = {
  getFloors(buildingId = null) {
    const params = new URLSearchParams()
    if (buildingId !== null && buildingId !== undefined && buildingId !== '') {
      params.set('building_id', String(buildingId))
    }
    const query = params.toString()
    return apiClient.get(`/floors/${query ? `?${query}` : ''}`)
  },

  getFloor(id) {
    return apiClient.get(`/floors/${id}`)
  },

  getFloorPlanUrl(id) {
    const baseUrl = normalizeBaseUrl(apiClient.defaults.baseURL || '')
    return `${baseUrl}/floors/${id}/plan`
  },

  createFloor(formData) {
    return apiClient.post('/floors/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  updateFloor(id, formData) {
    return apiClient.patch(`/floors/${id}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  deleteFloor(id) {
    return apiClient.delete(`/floors/${id}`)
  }
}
