import apiClient from './client'

export const authApi = {
  login(username, password) {
    const formData = new URLSearchParams()
    formData.set('username', username)
    formData.set('password', password)
    return apiClient.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    })
  },

  getMe() {
    return apiClient.get('/auth/me')
  }
}
