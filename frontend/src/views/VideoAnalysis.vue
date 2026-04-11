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
      <div class="header-actions">
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
            <div class="job-meta" v-if="job.reader_backend">Источник: {{ job.reader_backend }}</div>
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
              <p class="job-meta">
                {{ statusLabel(selectedJob.status) }} · {{ selectedJob.reader_backend || 'ожидание источника' }}
              </p>
            </div>
            <div class="details-actions">
              <button class="btn-text" :disabled="rerunning || isSelectedJobBusy" @click="rerunSelectedJob">
                <i class="pi pi-replay"></i>
                {{ rerunning ? 'Перезапуск...' : 'Повторный анализ' }}
              </button>
              <button class="btn-text" @click="refreshSelectedJob"><i class="pi pi-refresh"></i> Обновить</button>
            </div>
          </div>

          <div class="summary-grid">
            <div class="summary-card">
              <span>Статус</span>
              <strong>{{ statusLabel(selectedJob.status) }}</strong>
            </div>
            <div class="summary-card">
              <span>Проанализировано кадров</span>
              <strong>{{ selectedJob.analyzed_frames }}</strong>
            </div>
            <div class="summary-card">
              <span>Разрешено</span>
              <strong>{{ selectedJob.granted_count }}</strong>
            </div>
            <div class="summary-card">
              <span>Запрещено</span>
              <strong>{{ selectedJob.denied_count }}</strong>
            </div>
            <div class="summary-card">
              <span>Длительность видео</span>
              <strong>{{ formatSeconds(selectedJob.duration_sec) }}</strong>
            </div>
            <div class="summary-card">
              <span>Всего кадров</span>
              <strong>{{ selectedJob.total_frames ?? '—' }}</strong>
            </div>
          </div>

          <div v-if="selectedJob.error_message" class="error-box">
            <i class="pi pi-exclamation-triangle"></i>
            <span>{{ selectedJob.error_message }}</span>
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
            <article v-for="event in events" :key="event.id" class="event-card">
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
import { useUi } from '../services/ui'

const ui = useUi()
const jobs = ref([])
const events = ref([])
const selectedJob = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)
const jobsLoading = ref(false)
const eventsLoading = ref(false)
const rerunning = ref(false)

let refreshTimer = null

const hasProcessingJobs = computed(() => jobs.value.some((job) => ['queued', 'processing'].includes(job.status)))
const isSelectedJobBusy = computed(() => ['queued', 'processing'].includes(selectedJob.value?.status))

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

async function loadJobs({ keepSelection = true } = {}) {
  jobsLoading.value = true
  try {
    const response = await videoAnalysisApi.getJobs()
    jobs.value = response.data

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
  await loadEvents(jobId)
}

async function refreshSelectedJob() {
  if (!selectedJob.value) return
  try {
    const [jobRes, eventsRes] = await Promise.all([
      videoAnalysisApi.getJob(selectedJob.value.id),
      videoAnalysisApi.getJobEvents(selectedJob.value.id),
    ])

    selectedJob.value = jobRes.data
    const idx = jobs.value.findIndex((item) => item.id === selectedJob.value.id)
    if (idx !== -1) {
      jobs.value[idx] = jobRes.data
      jobs.value = [...jobs.value]
    }
    events.value = eventsRes.data
  } catch (error) {
    console.error('Ошибка обновления выбранной задачи:', error)
  }
}

async function rerunSelectedJob() {
  if (!selectedJob.value || isSelectedJobBusy.value) return
  rerunning.value = true
  try {
    const response = await videoAnalysisApi.rerunJob(selectedJob.value.id)
    selectedJob.value = response.data
    events.value = []
    const idx = jobs.value.findIndex((item) => item.id === response.data.id)
    if (idx !== -1) {
      jobs.value[idx] = response.data
      jobs.value = [...jobs.value]
    }
    startAutoRefresh()
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
  if (!selectedFile.value) return
  uploading.value = true
  try {
    const response = await videoAnalysisApi.createJob(selectedFile.value)
    selectedFile.value = null
    await loadJobs({ keepSelection: true })
    await selectJob(response.data.id)
    ui.success('Видео загружено, анализ запущен')
  } catch (error) {
    console.error('Ошибка запуска анализа видео:', error)
    ui.error(ui.getErrorMessage(error, 'Не удалось запустить анализ видео'))
  } finally {
    uploading.value = false
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  refreshTimer = setInterval(async () => {
    await loadJobs({ keepSelection: true })
    if (selectedJob.value && ['queued', 'processing'].includes(selectedJob.value.status)) {
      await refreshSelectedJob()
    }
    if (!hasProcessingJobs.value) {
      stopAutoRefresh()
    }
  }, 2500)
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

onMounted(async () => {
  await loadJobs({ keepSelection: false })
  startAutoRefresh()
})

onBeforeUnmount(() => {
  stopAutoRefresh()
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
