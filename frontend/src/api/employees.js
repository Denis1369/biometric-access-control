import apiClient from './client'

export const employeesApi = {
  getEmployees(skip = 0, limit = 100) {
    return apiClient.get(`/employees/?skip=${skip}&limit=${limit}`)
  },

  createEmployee(formData) {
    return apiClient.post('/employees/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  deleteEmployee(id) {
    return apiClient.delete(`/employees/${id}`)
  }
}