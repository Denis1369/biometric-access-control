import apiClient, { buildApiUrl } from './client'

export const videoAnalysisApi = {
  getJobs() {
    return apiClient.get('/video-analysis/jobs')
  },

  getJob(jobId) {
    return apiClient.get(`/video-analysis/jobs/${jobId}`)
  },

  getJobEvents(jobId) {
    return apiClient.get(`/video-analysis/jobs/${jobId}/events`)
  },

  rerunJob(jobId) {
    return apiClient.post(`/video-analysis/jobs/${jobId}/rerun`)
  },

  createJob(file) {
    const formData = new FormData()
    formData.append('video', file)
    return apiClient.post('/video-analysis/jobs', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  getEventPreviewUrl(eventId) {
    return buildApiUrl(`/video-analysis/events/${eventId}/preview`, { withToken: true })
  },
}
