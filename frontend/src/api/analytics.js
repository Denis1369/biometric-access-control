import apiClient from './client'

export const analyticsApi = {
  getStats() {
    return apiClient.get('/analytics/stats')
  },

  getAccessLogs(limit = 100) {
    return apiClient.get(`/analytics/access-logs?limit=${limit}`)
  }
}