import apiClient from './client'

export const analyticsApi = {
  getStats() { return apiClient.get('/analytics/stats') },
  getAccessLogs(limit = 100) { return apiClient.get(`/analytics/access-logs?limit=${limit}`) },
  getDailyChart() { return apiClient.get('/analytics/daily-chart') },
  getMonthlyDepartmentChart() { return apiClient.get('/analytics/monthly-department-chart') },
  getMonthlyDaysChart() { return apiClient.get('/analytics/monthly-days-chart') },
  getPresence() { return apiClient.get('/analytics/presence') },
  getCameraTraffic() { return apiClient.get('/analytics/camera-traffic') },
  getDiscipline() { return apiClient.get('/analytics/discipline') }
}