import apiClient, { buildApiUrl } from './client'

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
    return buildApiUrl(`/floors/${id}/plan`, { withToken: true })
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

  analyzePlan(id) {
    return apiClient.get(`/floors/${id}/plan-analysis`)
  },
}
