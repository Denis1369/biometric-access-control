import apiClient from './client'

function normalizeBaseUrl(url) {
  if (!url) return ''
  return url.endsWith('/') ? url.slice(0, -1) : url
}

export const guestsApi = {
  getGuests() {
    return apiClient.get('/guests/')
  },

  getGuestPhotoUrl(photoId) {
    if (!photoId) return ''
    const baseUrl = normalizeBaseUrl(apiClient.defaults.baseURL || '')
    return `${baseUrl}/guests/photo/${photoId}`
  },

  createGuest(formData) {
    return apiClient.post('/guests/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  deactivateGuest(id) {
    return apiClient.patch(`/guests/${id}/deactivate`)
  },

  deleteGuest(id) {
    return apiClient.delete(`/guests/${id}`)
  }
}