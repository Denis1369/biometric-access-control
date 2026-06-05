import apiClient, { buildApiUrl } from './client'

/**
 * API страницы “Анализ видео”.
 *
 * Этот раздел работает с одним загруженным видеофайлом: frontend создаёт job,
 * backend в фоне анализирует кадры, создаёт события доступа и сохраняет
 * preview-кадры. Прогресс job дополнительно приходит через WebSocket.
 */
export const videoAnalysisApi = {
  /** Получить список ранее созданных заданий анализа видео. */
  getJobs() {
    return apiClient.get('/video-analysis/jobs')
  },

  /** Получить состояние одного задания: статус, прогресс, счётчики и ошибку. */
  getJob(jobId) {
    return apiClient.get(`/video-analysis/jobs/${jobId}`)
  },

  /** Получить события распознавания, найденные внутри обработанного видео. */
  getJobEvents(jobId) {
    return apiClient.get(`/video-analysis/jobs/${jobId}/events`)
  },

  /**
   * Собрать URL исходного видео для тега `<video>`.
   *
   * Так как видео открывается браузером напрямую, JWT добавляется в query, а не
   * через axios interceptor.
   */
  getJobVideoUrl(jobId) {
    return buildApiUrl(`/video-analysis/jobs/${jobId}/source-video`, { withToken: true })
  },

  /** Очистить старые события и запустить обработку того же видео повторно. */
  rerunJob(jobId) {
    return apiClient.post(`/video-analysis/jobs/${jobId}/rerun`)
  },

  /**
   * Создать новое задание анализа видео из выбранного пользователем файла.
   *
   * Видео отправляется как multipart/form-data, потому что backend принимает
   * файл целиком и сохраняет его во временное хранилище перед фоновой обработкой.
   */
  createJob(file) {
    const formData = new FormData()
    formData.append('video', file)
    return apiClient.post('/video-analysis/jobs', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  /** Получить URL preview-кадра конкретного события анализа. */
  getEventPreviewUrl(eventId) {
    return buildApiUrl(`/video-analysis/events/${eventId}/preview`, { withToken: true })
  },
}
