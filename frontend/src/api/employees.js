import apiClient from './client'

function normalizeBaseUrl(url) {
  if (!url) return ''
  return url.endsWith('/') ? url.slice(0, -1) : url
}

export const employeesApi = {
  getEmployees(skip = 0, limit = 100) {
    return apiClient.get(`/employees/?skip=${skip}&limit=${limit}`)
  },

  getEmployee(id) {
    return apiClient.get(`/employees/${id}`)
  },

  getFaceSamplePhotoUrl(sampleId) {
    const baseUrl = normalizeBaseUrl(apiClient.defaults.baseURL || '')
    return `${baseUrl}/employees/face-samples/${sampleId}/photo`
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
  },

  deleteEmployee(id) {
    return apiClient.delete(`/employees/${id}`)
  }
}