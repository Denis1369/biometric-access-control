import apiClient from './client'

export const jobPositionsApi = {
  getJobPositions(includeInactive = false) {
    const suffix = includeInactive ? '' : '?only_active=true'
    return apiClient.get(`/job-positions/${suffix}`)
  },

  createJobPosition(payload) {
    return apiClient.post('/job-positions/', payload)
  },

  updateJobPosition(id, payload) {
    return apiClient.patch(`/job-positions/${id}`, payload)
  }
}
