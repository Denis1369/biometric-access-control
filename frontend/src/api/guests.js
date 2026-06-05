import apiClient, { buildApiUrl } from './client'

/**
 * API гостевых пропусков.
 *
 * Гость в системе состоит не только из ФИО и срока действия пропуска. При
 * создании можно загрузить фото лица для распознавания на проходной и фото
 * полного роста для Re-ID, чтобы позже строить маршрут гостя по камерам.
 */
export const guestsApi = {
  /** Получить список гостей и их признаки: активен ли пропуск, есть ли фото и body embedding. */
  getGuests() {
    return apiClient.get('/guests/')
  },

  /**
   * Собрать URL фотографии лица гостя.
   *
   * Фотография открывается как обычный ресурс браузера, поэтому токен кладётся
   * в query-параметр, а не в HTTP-заголовок axios.
   */
  getGuestPhotoUrl(photoId) {
    if (!photoId) return ''
    return buildApiUrl(`/guests/photo/${photoId}`, { withToken: true })
  },

  /**
   * Создать гостевой пропуск из multipart-формы.
   *
   * `formData` может содержать текстовые поля гостя, `face_photo` и
   * `body_photo`. Backend сохранит Guest, GuestFaceSample и при наличии фото
   * полного роста рассчитает `body_embedding`.
   */
  createGuest(formData) {
    return apiClient.post('/guests/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  /**
   * Дозагрузить или заменить фото полного роста гостя.
   *
   * Используется, когда пропуск уже создан, но для построения маршрута не хватает
   * Re-ID признаков. Backend не хранит само фото полного роста, а извлекает из
   * него новый `body_embedding`.
   */
  uploadBodyPhoto(id, formData) {
    return apiClient.post(`/guests/${id}/body-photo`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  /** Аннулировать пропуск гостя без удаления истории журналов. */
  deactivateGuest(id) {
    return apiClient.patch(`/guests/${id}/deactivate`)
  },
}
