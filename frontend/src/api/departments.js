import apiClient from './client'

export const departmentsApi = {
  getDepartments() {
    return apiClient.get('/departments/')
  }
}