import apiClient from './client'

function buildQuery(params) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  })
  const query = search.toString()
  return query ? `?${query}` : ''
}

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
  getDiscipline() { return apiClient.get('/analytics/discipline') },
  
  getDailyGuests(date = null) {
    const query = date ? `?target_date=${date}` : ''
    return apiClient.get(`/analytics/daily-guests${query}`)
  },

  getGuestRoute({ guestId = null, targetDate = null, buildingId = null, floorId = null, limit = 200 } = {}) {
    const query = buildQuery({
      guest_id: guestId,
      target_date: targetDate,
      building_id: buildingId,
      floor_id: floorId,
      limit,
    })
    return apiClient.get(`/analytics/guest-route${query}`)
  },

  getCameraTransitions({
    targetDate = null,
    days = 30,
    buildingId = null,
    floorId = null,
    personType = 'all',
    maxGapMinutes = 30,
    minCount = 1,
    limit = 100,
  } = {}) {
    const query = buildQuery({
      target_date: targetDate,
      days,
      building_id: buildingId,
      floor_id: floorId,
      person_type: personType,
      max_gap_minutes: maxGapMinutes,
      min_count: minCount,
      limit,
    })
    return apiClient.get(`/analytics/camera-transitions${query}`)
  }
}
