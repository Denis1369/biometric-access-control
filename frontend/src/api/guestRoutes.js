import apiClient from './client'

function buildQuery(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  })
  const query = search.toString()
  return query ? `?${query}` : ''
}

export const guestRoutesApi = {
  getCameraRouteCandidates(floorId) {
    return apiClient.get(`/floors/${floorId}/camera-route-candidates`)
  },

  getGuestProbableRoute(floorId, guestId, params = {}) {
    return apiClient.get(`/floors/${floorId}/guests/${guestId}/probable-route${buildQuery(params)}`)
  },
}
