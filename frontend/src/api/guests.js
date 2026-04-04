import apiClient, { buildApiUrl } from './client'

export const guestsApi = {
  getGuests() {
    return apiClient.get('/guests/')
  },

  getGuestPhotoUrl(photoId) {
    if (!photoId) return ''
    return buildApiUrl(`/guests/photo/${photoId}`, { withToken: true })
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