import apiClient from './client'

export const analyticsApi = {
  getStats(date = null) { 
    const query = date ? `?target_date=${date}` : ''
    return apiClient.get(`/analytics/stats${query}`) 
  },
  getAccessLogs(limit = 100) { return apiClient.get(`/analytics/access-logs?limit=${limit}`) },
  getDailyChart(date = null) { 
    const query = date ? `?target_date=${date}` : ''
    return apiClient.get(`/analytics/daily-chart${query}`) 
  },
  getMonthlyDepartmentChart() { return apiClient.get('/analytics/monthly-department-chart') },
  getMonthlyDaysChart() { return apiClient.get('/analytics/monthly-days-chart') },
  getPresence(date = null) { 
    const query = date ? `?target_date=${date}` : ''
    return apiClient.get(`/analytics/presence${query}`) 
  },
  getCameraTraffic() { return apiClient.get('/analytics/camera-traffic') },
  getDailyAttendance(date = null) { 
    const query = date ? `?target_date=${date}` : ''
    return apiClient.get(`/analytics/daily-attendance${query}`) 
  },
  getDiscipline() { return apiClient.get('/analytics/discipline') }
}