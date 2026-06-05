<template>
  <div class="page-container">
    <div class="header-panel">
      <div>
        <h1 class="page-title">Анализ загруженного видео</h1>
        <p class="page-subtitle">
          Загрузите короткий ролик с проходной. Система разберёт кадры, покажет разрешённые и запрещённые события
          и сохранит превью для защиты практики.
        </p>
      </div>
      <div v-if="canManageVideoAnalysis" class="header-actions">
        <label class="upload-btn">
          <input type="file" accept="video/mp4,video/avi,video/mov,video/mkv,video/webm" @change="onFileChange" hidden />
          <i class="pi pi-upload"></i>
          Выбрать видео
        </label>
        <button class="btn-primary" :disabled="!selectedFile || uploading" @click="uploadVideo">
          <i class="pi pi-play"></i>
          {{ uploading ? 'Загрузка...' : 'Запустить анализ' }}
        </button>
      </div>
    </div>

    <div class="upload-hint" v-if="selectedFile">
      <i class="pi pi-file"></i>
      <span>{{ selectedFile.name }}</span>
      <small>({{ formatBytes(selectedFile.size) }})</small>
    </div>

    <div class="analysis-grid">
      <section class="jobs-panel">
        <div class="section-head">
          <h2>Задачи</h2>
          <button class="btn-text" @click="loadJobs"><i class="pi pi-refresh"></i> Обновить</button>
        </div>

        <div v-if="jobsLoading" class="panel-placeholder">
          <i class="pi pi-spin pi-spinner"></i>
          <p>Загрузка задач...</p>
        </div>

        <div v-else-if="jobs.length === 0" class="panel-placeholder">
          <i class="pi pi-video"></i>
          <p>Пока нет задач анализа.</p>
        </div>

        <div v-else class="jobs-list">
          <button
            v-for="job in jobs"
            :key="job.id"
            class="job-card"
            :class="{ active: selectedJob?.id === job.id }"
            @click="selectJob(job.id)"
          >
            <div class="job-top">
              <strong>{{ job.original_filename }}</strong>
              <span class="status-badge" :class="job.status">{{ statusLabel(job.status) }}</span>
            </div>
            <div class="job-meta">Создано: {{ formatDateTime(job.created_at) }}</div>
            <div class="job-stats">
              <span>Разрешено: {{ job.granted_count }}</span>
              <span>Запрещено: {{ job.denied_count }}</span>
            </div>
          </button>
        </div>
      </section>

      <section class="details-panel">
        <div v-if="!selectedJob" class="panel-placeholder big">
          <i class="pi pi-info-circle"></i>
          <p>Выберите задачу слева, чтобы увидеть события.</p>
        </div>

        <template v-else>
          <div class="section-head details-head">
            <div>
              <h2>{{ selectedJob.original_filename }}</h2>
              <p class="job-meta">{{ statusLabel(selectedJob.status) }}</p>
            </div>
            <div class="details-actions">
              <button v-if="canManageVideoAnalysis" class="btn-text" :disabled="rerunning || isSelectedJobBusy" @click="rerunSelectedJob">
                <i class="pi pi-replay"></i>
                {{ rerunning ? 'Перезапуск...' : 'Повторный анализ' }}
              </button>
              <button class="btn-text" @click="loadEvents(selectedJob.id)">
                <i class="pi pi-refresh"></i>
                Обновить события
              </button>
            </div>
          </div>

          <div class="summary-grid">
            <div class="summary-card">
              <span>Статус</span>
              <strong>{{ statusLabel(selectedJob.status) }}</strong>
            </div>
            <div class="summary-card">
              <span>Разрешено</span>
              <strong>{{ selectedJob.granted_count }}</strong>
            </div>
            <div class="summary-card">
              <span>Запрещено</span>
              <strong>{{ selectedJob.denied_count }}</strong>
            </div>
          </div>

          <div v-if="selectedJob.error_message" class="error-box">
            <i class="pi pi-exclamation-triangle"></i>
            <span>{{ selectedJob.error_message }}</span>
          </div>

          <div class="source-video-panel">
            <div class="source-video-head">
              <div>
                <h3>Исходное видео</h3>
                <p class="job-meta">Кнопка события перематывает видео к нужному кадру.</p>
              </div>
              <span v-if="highlightedEventId" class="seek-chip">Кадр выбран</span>
            </div>
            <video
              ref="videoPlayer"
              :key="selectedJob.id"
              class="source-video"
              :src="selectedJobVideoUrl"
              controls
              preload="metadata"
            ></video>
          </div>

          <div class="section-head events-head">
            <h3>События распознавания</h3>
            <span class="job-meta">{{ events.length }} событий</span>
          </div>

          <div v-if="eventsLoading" class="panel-placeholder big">
            <i class="pi pi-spin pi-spinner"></i>
            <p>Загрузка событий...</p>
          </div>

          <div v-else-if="events.length === 0" class="panel-placeholder big">
            <i class="pi pi-images"></i>
            <p>События пока не найдены.</p>
          </div>

          <div v-else class="events-grid">
            <article
              v-for="event in events"
              :key="event.id"
              class="event-card"
              :class="{ selected: highlightedEventId === event.id }"
            >
              <img :src="getPreviewUrl(event.id)" alt="event preview" class="event-preview" />
              <div class="event-body">
                <div class="event-top">
                  <span class="status-badge" :class="event.status">{{ eventStatusLabel(event.status) }}</span>
                  <strong>{{ formatSeconds(event.timestamp_sec) }}</strong>
                </div>
                <div class="event-title">{{ event.person_name || 'Неизвестное лицо' }}</div>
                <div class="event-meta">Кадр: {{ event.frame_index }}</div>
                <div class="event-meta">Решение: {{ decisionLabel(event.decision) }}</div>
                <div class="event-meta" v-if="event.confidence !== null && event.confidence !== undefined">
                  Похожесть: {{ Math.round(event.confidence * 100) }}%
                </div>
                <button class="btn-seek-frame" @click="seekToEvent(event)">
                  <i class="pi pi-step-forward"></i>
                  Перейти к этому кадру
                </button>
              </div>
            </article>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { videoAnalysisApi } from '../api/videoAnalysis'
import { PERMISSIONS } from '../constants/roles'
import { createJsonWebSocket } from '../services/jsonWebSocket'
import { useAuth } from '../services/auth'
import { useUi } from '../services/ui'

/**
 * Страница анализа загруженных видеофайлов.
 *
 * Пользователь загружает видео, backend создаёт `VideoAnalysisJob`, а затем
 * фоновый сервис анализирует кадры: ищет лица, сравнивает их с сотрудниками и
 * гостями, сохраняет события и preview-кадры. Страница подписывается на
 * WebSocket конкретного задания, чтобы показывать прогресс без polling.
 *
 * Этот раздел отличается от маршрута гостя: здесь анализируется один
 * загруженный файл как самостоятельное задание, а не набор file-камер этажа.
 */
const ui = useUi()
const auth = useAuth()
const canManageVideoAnalysis = computed(() => auth.hasPermission(PERMISSIONS.VIDEO_ANALYSIS_WRITE))
const jobs = ref([])
const events = ref([])
const selectedJob = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)
const jobsLoading = ref(false)
const eventsLoading = ref(false)
const rerunning = ref(false)
const videoPlayer = ref(null)
const highlightedEventId = ref(null)

const jobSockets = new Map()

const isSelectedJobBusy = computed(() => ['queued', 'processing'].includes(selectedJob.value?.status))
const selectedJobVideoUrl = computed(() => (
  selectedJob.value ? videoAnalysisApi.getJobVideoUrl(selectedJob.value.id) : ''
))

function isRunningJob(job) {
  return ['queued', 'processing'].includes(job?.status)
}

function upsertJob(job) {
  const index = jobs.value.findIndex((item) => item.id === job.id)
  if (index === -1) {
    jobs.value = [job, ...jobs.value]
  } else {
    jobs.value[index] = job
    jobs.value = [...jobs.value]
  }

  if (selectedJob.value?.id === job.id) {
    selectedJob.value = job
  }
}

function closeJobSocket(jobId) {
  const socket = jobSockets.get(jobId)
  if (!socket) return
  socket.close()
  jobSockets.delete(jobId)
}

function closeAllJobSockets() {
  for (const jobId of jobSockets.keys()) {
    closeJobSocket(jobId)
  }
}

function subscribeJob(jobId) {
  if (jobSockets.has(jobId)) return

  const socket = createJsonWebSocket({
    path: `/ws/video-analysis/jobs/${jobId}`,
    onMessage: (job) => {
      upsertJob(job)
      if (selectedJob.value?.id === job.id) {
        void loadEvents(job.id)
      }
      if (!isRunningJob(job)) {
        closeJobSocket(job.id)
      }
    },
    onError: (error) => {
      closeJobSocket(jobId)
      ui.error(ui.getErrorMessage(error, 'WebSocket статуса анализа видео недоступен'))
    },
  })
  jobSockets.set(jobId, socket)
}

function syncJobSubscriptions() {
  jobs.value.filter(isRunningJob).forEach((job) => subscribeJob(job.id))

  for (const jobId of jobSockets.keys()) {
    const job = jobs.value.find((item) => item.id === jobId)
    if (!isRunningJob(job)) {
      closeJobSocket(jobId)
    }
  }
}

function statusLabel(status) {
  return {
    queued: 'В очереди',
    processing: 'Обработка',
    completed: 'Завершено',
    failed: 'Ошибка',
  }[status] || status
}

function eventStatusLabel(status) {
  return status === 'granted' ? 'Разрешено' : 'Запрещено'
}

function decisionLabel(decision) {
  return {
    auto_allow: 'Автодопуск',
    review: 'Требует проверки',
    denied: 'Отказ',
  }[decision] || '—'
}

function formatDateTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('ru-RU')
}

function formatSeconds(value) {
  if (value === null || value === undefined) return '—'
  return `${Number(value).toFixed(2)} сек`
}

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`
}

function getPreviewUrl(eventId) {
  return videoAnalysisApi.getEventPreviewUrl(eventId)
}

function seekToEvent(event) {
  const player = videoPlayer.value
  if (!player) {
    ui.warn('Видео ещё не готово к перемотке')
    return
  }

  const targetTime = Math.max(0, Number(event.timestamp_sec) || 0)
  highlightedEventId.value = event.id

  const seek = () => {
    player.currentTime = Math.min(targetTime, player.duration || targetTime)
    player.pause()
    player.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  if (Number.isFinite(player.duration) && player.duration > 0) {
    seek()
    return
  }

  player.addEventListener('loadedmetadata', seek, { once: true })
  player.load()
}

async function loadJobs({ keepSelection = true } = {}) {
  jobsLoading.value = true
  try {
    const response = await videoAnalysisApi.getJobs()
    jobs.value = response.data
    syncJobSubscriptions()

    if (!keepSelection) {
      selectedJob.value = jobs.value[0] || null
      if (selectedJob.value) {
        await loadEvents(selectedJob.value.id)
      }
      return
    }

    if (!selectedJob.value && jobs.value.length > 0) {
      await selectJob(jobs.value[0].id)
      return
    }

    if (selectedJob.value) {
      const actual = jobs.value.find((job) => job.id === selectedJob.value.id)
      if (actual) {
        selectedJob.value = actual
      }
    }
  } catch (error) {
    console.error('Ошибка загрузки задач анализа:', error)
  } finally {
    jobsLoading.value = false
  }
}

async function loadEvents(jobId) {
  eventsLoading.value = true
  try {
    const response = await videoAnalysisApi.getJobEvents(jobId)
    events.value = response.data
  } catch (error) {
    console.error('Ошибка загрузки событий анализа:', error)
  } finally {
    eventsLoading.value = false
  }
}

async function selectJob(jobId) {
  const job = jobs.value.find((item) => item.id === jobId)
  if (!job) return
  selectedJob.value = job
  highlightedEventId.value = null
  if (isRunningJob(job)) {
    subscribeJob(job.id)
  }
  await loadEvents(jobId)
}

async function rerunSelectedJob() {
  if (!canManageVideoAnalysis.value) return
  if (!selectedJob.value || isSelectedJobBusy.value) return
  rerunning.value = true
  try {
    const response = await videoAnalysisApi.rerunJob(selectedJob.value.id)
    events.value = []
    upsertJob(response.data)
    subscribeJob(response.data.id)
  } catch (error) {
    console.error('Ошибка повторного анализа видео:', error)
    ui.error(ui.getErrorMessage(error, 'Не удалось повторно запустить анализ'))
  } finally {
    rerunning.value = false
  }
}

function onFileChange(event) {
  const [file] = event.target.files || []
  selectedFile.value = file || null
}

async function uploadVideo() {
  if (!canManageVideoAnalysis.value) return
  if (!selectedFile.value) return
  uploading.value = true
  try {
    const response = await videoAnalysisApi.createJob(selectedFile.value)
    selectedFile.value = null
    upsertJob(response.data)
    subscribeJob(response.data.id)
    await selectJob(response.data.id)
    ui.success('Видео загружено, анализ запущен')
  } catch (error) {
    console.error('Ошибка запуска анализа видео:', error)
    ui.error(ui.getErrorMessage(error, 'Не удалось запустить анализ видео'))
  } finally {
    uploading.value = false
  }
}

onMounted(async () => {
  await loadJobs({ keepSelection: false })
})

onBeforeUnmount(() => {
  closeAllJobSockets()
})
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.header-panel {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.page-title {
  font-size: 1.85rem;
  color: #0f172a;
  margin-bottom: 0.25rem;
}

.page-subtitle {
  color: #64748b;
  max-width: 860px;
  line-height: 1.5;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.details-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.upload-btn,
.btn-primary,
.btn-text {
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.upload-btn {
  background: #e2e8f0;
  color: #0f172a;
  padding: 0.85rem 1rem;
}

.btn-primary {
  background: #10b981;
  color: white;
  padding: 0.85rem 1rem;
}

.btn-primary:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.btn-text:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-text {
  background: #f1f5f9;
  color: #334155;
  padding: 0.65rem 0.9rem;
}

.upload-hint {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: #ecfeff;
  color: #0f766e;
  border: 1px solid #a5f3fc;
  padding: 0.85rem 1rem;
  border-radius: 12px;
  width: fit-content;
}

.analysis-grid {
  display: grid;
  grid-template-columns: 330px minmax(0, 1fr);
  gap: 1.5rem;
  min-height: 640px;
}

.jobs-panel,
.details-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.jobs-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  overflow-y: auto;
}

.job-card {
  width: 100%;
  text-align: left;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 14px;
  padding: 0.9rem;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.job-card.active {
  border-color: #10b981;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.12);
}

.job-top,
.event-top {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  align-items: center;
}

.job-meta,
.event-meta {
  color: #64748b;
  font-size: 0.88rem;
}

.job-stats {
  display: flex;
  gap: 0.75rem;
  font-size: 0.9rem;
  color: #334155;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  padding: 0.35rem 0.7rem;
  font-size: 0.8rem;
  font-weight: 700;
}

.status-badge.queued {
  background: #e2e8f0;
  color: #334155;
}

.status-badge.processing {
  background: #dbeafe;
  color: #1d4ed8;
}

.status-badge.completed,
.status-badge.granted {
  background: #dcfce7;
  color: #166534;
}

.status-badge.failed,
.status-badge.denied {
  background: #fee2e2;
  color: #991b1b;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.85rem;
}

.summary-card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 1rem;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.summary-card span {
  color: #64748b;
  font-size: 0.84rem;
}

.summary-card strong {
  font-size: 1.1rem;
  color: #0f172a;
}

.error-box {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  background: #fff1f2;
  color: #be123c;
  border: 1px solid #fecdd3;
  padding: 0.9rem 1rem;
  border-radius: 12px;
}

.source-video-panel {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  border: 1px solid #dbeafe;
  border-radius: 16px;
  padding: 1rem;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.source-video-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.source-video-head h3 {
  margin: 0 0 0.25rem;
  color: #0f172a;
}

.seek-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #dcfce7;
  color: #166534;
  padding: 0.35rem 0.7rem;
  font-size: 0.78rem;
  font-weight: 800;
}

.source-video {
  width: 100%;
  max-height: 520px;
  border-radius: 14px;
  background: #020617;
  box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.25);
}

.events-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 420px));
  gap: 1rem;
  align-content: start;
}

.event-card {
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  overflow: hidden;
  background: #fff;
  max-width: 420px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.event-card.selected {
  border-color: #2563eb;
  box-shadow: 0 14px 30px rgba(37, 99, 235, 0.18);
  transform: translateY(-2px);
}

.event-preview {
  width: 100%;
  aspect-ratio: 4 / 5;
  object-fit: contain;
  object-position: center top;
  display: block;
  background: #e2e8f0;
}

.event-body {
  padding: 0.95rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.event-title {
  font-size: 1rem;
  font-weight: 700;
  color: #0f172a;
}

.btn-seek-frame {
  margin-top: 0.35rem;
  border: 1px solid #bfdbfe;
  border-radius: 10px;
  background: #eff6ff;
  color: #1d4ed8;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  padding: 0.65rem 0.8rem;
  font-weight: 800;
}

.btn-seek-frame:hover {
  border-color: #60a5fa;
  background: #dbeafe;
}

.panel-placeholder {
  border: 1px dashed #cbd5e1;
  border-radius: 14px;
  padding: 2rem 1rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  color: #64748b;
  text-align: center;
}

.panel-placeholder.big {
  min-height: 320px;
}

@media (max-width: 1200px) {
  .analysis-grid {
    grid-template-columns: 1fr;
  }

  .events-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
