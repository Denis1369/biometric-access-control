import apiClient from './client'

export const usersApi = {
  getUsers() {
    return apiClient.get('/users/')
  },

  createUser(payload) {
    return apiClient.post('/users/', payload)
  },

  updateUser(id, payload) {
    return apiClient.patch(`/users/${id}`, payload)
  }
}
