import apiClient from './client'

export const departmentsApi = {
  getDepartments() {
    return apiClient.get('/departments/')
  },
  createDepartment(payload) {
    return apiClient.post('/departments/', payload)
  },
  updateDepartment(id, payload) {
    return apiClient.patch(`/departments/${id}`, payload)
  },

  applyGlobalSchedule(payload) {
    return apiClient.post('/departments/apply-global-schedule', payload)
  }
}