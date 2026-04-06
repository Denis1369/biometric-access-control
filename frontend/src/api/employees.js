import apiClient, { buildApiUrl } from './client'

export const employeesApi = {
  getEmployees(skip = 0, limit = 100) {
    return apiClient.get(`/employees/?skip=${skip}&limit=${limit}`)
  },

  getEmployee(id) {
    return apiClient.get(`/employees/${id}`)
  },

  getFaceSamplePhotoUrl(sampleId) {
    return buildApiUrl(`/employees/face-samples/${sampleId}/photo`, { withToken: true })
  },

  createEmployee(formData) {
    return apiClient.post('/employees/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  updateEmployee(id, formData) {
    return apiClient.patch(`/employees/${id}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  }
}
