<template>
  <div class="monitoring-page">
    <section class="monitoring-hero">
      <div class="hero-left">
        <div class="hero-badge">
          <span class="hero-dot" :class="{ active: !!selectedCamera }"></span>
          Мониторинг проходной
        </div>
        <h1 class="hero-title">Онлайн-наблюдение и события доступа</h1>
        <p class="hero-subtitle">
          Выберите камеру и просматривайте поток вместе с журналом событий в реальном времени.
        </p>
      </div>

      <div class="hero-right">
        <div class="hero-actions">
          <select
            v-model="selectedCameraId"
            @change="startVideoFeed"
            class="camera-select"
          >
            <option value="" disabled>Выберите камеру...</option>
            <option v-for="cam in cameras" :key="cam.id" :value="cam.id">
              {{ cam.name }} ({{ cam.ip_address }})
            </option>
          </select>

          <button class="secondary-btn" @click="loadCameras">
            Обновить
          </button>
        </div>

        <div class="hero-status">
          <div class="status-pill" :class="videoStatusClass">
            <span class="status-dot"></span>
            {{ videoStatusText }}
          </div>
          <div class="status-pill events">
            <span class="status-dot"></span>
            Событий: {{ liveEvents.length }}
          </div>
        </div>
      </div>
    </section>

    <section class="monitoring-grid">
      <div class="glass-card video-card">
        <div class="card-head">
          <div>
            <div class="card-label">Видеопоток</div>
            <h2 class="card-title">
              {{ selectedCamera?.name || 'Камера не выбрана' }}
            </h2>
          </div>

          <div v-if="selectedCamera" class="camera-meta">
            <span class="meta-chip">{{ selectedCamera.ip_address }}</span>
          </div>
        </div>

        <div class="video-shell">
          <img
            v-if="currentFrame"
            :src="currentFrame"
            alt="Live stream"
            class="live-video"
          />

          <div v-else class="video-placeholder">
            <div class="placeholder-icon-wrap">
              <i class="pi pi-video placeholder-icon"></i>
            </div>
            <div class="placeholder-title">
              {{ selectedCameraId ? 'Подключение к камере...' : 'Камера не выбрана' }}
            </div>
            <div class="placeholder-text">
              {{
                selectedCameraId
                  ? 'Ожидаем первый кадр потока'
                  : 'Выберите активную камеру для начала просмотра'
              }}
            </div>
          </div>

          <div class="video-overlay">
            <div class="overlay-badge">
              <span class="overlay-dot" :class="{ active: !!currentFrame }"></span>
              {{ currentFrame ? 'LIVE' : 'WAITING' }}
            </div>
          </div>
        </div>
      </div>

      <div class="glass-card events-card">
        <div class="card-head">
          <div>
            <div class="card-label">Журнал доступа</div>
            <h2 class="card-title">События в реальном времени</h2>
          </div>
        </div>

        <div class="events-list">
          <div
            v-for="(event, index) in liveEvents"
            :key="index"
            :class="['event-item', event.status === 'granted' ? 'success' : 'danger']"
          >
            <div class="event-icon-wrap">
              <i
                :class="event.status === 'granted'
                  ? 'pi pi-check-circle'
                  : 'pi pi-times-circle'"
              ></i>
            </div>

            <div class="event-content">
              <div class="event-top">
                <span class="event-status">
                  {{ event.status === 'granted' ? 'Доступ разрешён' : 'Доступ запрещён' }}
                </span>
                <span class="event-time">{{ event.time }}</span>
              </div>
              <div class="event-message">{{ event.message }}</div>
            </div>
          </div>

          <div v-if="liveEvents.length === 0" class="empty-state">
            <div class="empty-icon-wrap">
              <i class="pi pi-inbox empty-icon"></i>
            </div>
            <div class="empty-title">Пока нет событий</div>
            <div class="empty-text">
              После запуска системы здесь будут отображаться события проходной.
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { camerasApi } from '../api/cameras'

const cameras = ref([])
const selectedCameraId = ref('')

const currentFrame = ref(null)
const liveEvents = ref([])

let videoWs = null
let eventsWs = null
let lastVideoBlobUrl = null
const lastGrantedByEmployee = new Map()

const selectedCamera = computed(() => {
  return cameras.value.find(cam => String(cam.id) === String(selectedCameraId.value)) || null
})

const videoStatusText = computed(() => {
  if (!selectedCameraId.value) return 'Камера не выбрана'
  if (currentFrame.value) return 'Поток активен'
  return 'Подключение...'
})

const videoStatusClass = computed(() => {
  if (!selectedCameraId.value) return 'idle'
  if (currentFrame.value) return 'online'
  return 'connecting'
})

const loadCameras = async () => {
  try {
    const response = await camerasApi.getCameras()
    cameras.value = response.data.filter(c => c.is_active)
  } catch (error) {
    console.error('Ошибка загрузки камер', error)
  }
}

const clearCurrentFrame = () => {
  currentFrame.value = null

  if (lastVideoBlobUrl) {
    URL.revokeObjectURL(lastVideoBlobUrl)
    lastVideoBlobUrl = null
  }
}

const stopVideoFeed = () => {
  if (videoWs) {
    videoWs.close()
    videoWs = null
  }

  clearCurrentFrame()
}

const startVideoFeed = () => {
  stopVideoFeed()

  if (!selectedCameraId.value) return

  const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const apiHost = `${window.location.hostname}:8000`

  videoWs = new WebSocket(`${wsProtocol}://${apiHost}/ws/video/${selectedCameraId.value}`)
  videoWs.binaryType = 'blob'

  videoWs.onopen = () => {
    console.log('Video WS opened')
  }

  videoWs.onmessage = (event) => {
    if (lastVideoBlobUrl) {
      URL.revokeObjectURL(lastVideoBlobUrl)
    }

    lastVideoBlobUrl = URL.createObjectURL(event.data)
    currentFrame.value = lastVideoBlobUrl
  }

  videoWs.onerror = (error) => {
    console.error('Video WS error', error)
  }

  videoWs.onclose = (event) => {
    console.log('Video WS closed', event.code, event.reason)
  }
}

const startEventsFeed = () => {
  if (eventsWs) {
    eventsWs.close()
    eventsWs = null
  }

  const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const apiHost = `${window.location.hostname}:8000`

  eventsWs = new WebSocket(`${wsProtocol}://${apiHost}/ws/events`)

  eventsWs.onmessage = (event) => {
    const data = JSON.parse(event.data)

    if (data.status !== 'granted') {
      return
    }

    const now = Date.now()
    const employeeKey = data.employee_id ?? 'unknown'
    const lastTime = lastGrantedByEmployee.get(employeeKey) ?? 0

    if (now - lastTime < 5000) {
      return
    }

  lastGrantedByEmployee.set(employeeKey, now)

    const newEvent = {
      ...data,
      time: new Date().toLocaleTimeString('ru-RU')
    }

    liveEvents.value.unshift(newEvent)

    if (liveEvents.value.length > 20) {
      liveEvents.value.pop()
    }
  }

  eventsWs.onerror = (error) => {
    console.error('Events WS error', error)
  }

  eventsWs.onclose = (event) => {
    console.log('Events WS closed', event.code, event.reason)
  }
}

onMounted(() => {
  loadCameras()
  startEventsFeed()
})

onBeforeUnmount(() => {
  stopVideoFeed()

  if (eventsWs) {
    eventsWs.close()
    eventsWs = null
  }
})
</script>

<style scoped>
.monitoring-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.monitoring-hero {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: 1.25rem;
  padding: 1.5rem;
  border-radius: 28px;
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.14), transparent 36%),
    radial-gradient(circle at bottom right, rgba(16, 185, 129, 0.12), transparent 32%),
    #ffffff;
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.06);
}

.hero-left,
.hero-right {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  width: fit-content;
  padding: 0.5rem 0.9rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.05);
  color: #334155;
  font-size: 0.9rem;
  font-weight: 600;
  margin-bottom: 1rem;
}

.hero-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #94a3b8;
  box-shadow: 0 0 0 6px rgba(148, 163, 184, 0.12);
}

.hero-dot.active {
  background: #10b981;
  box-shadow: 0 0 0 6px rgba(16, 185, 129, 0.14);
}

.hero-title {
  margin: 0;
  font-size: 2rem;
  line-height: 1.15;
  font-weight: 800;
  color: #0f172a;
}

.hero-subtitle {
  margin: 0.75rem 0 0;
  font-size: 1rem;
  line-height: 1.65;
  color: #64748b;
  max-width: 720px;
}

.hero-actions {
  display: flex;
  gap: 0.85rem;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.camera-select {
  min-width: 320px;
  height: 48px;
  padding: 0 1rem;
  border-radius: 16px;
  border: 1px solid #dbe4ee;
  background: rgba(248, 250, 252, 0.92);
  color: #0f172a;
  font-size: 0.96rem;
  outline: none;
  transition: 0.2s ease;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75);
}

.camera-select:focus {
  border-color: rgba(59, 130, 246, 0.45);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.08);
}

.secondary-btn {
  height: 48px;
  padding: 0 1rem;
  border: none;
  border-radius: 16px;
  background: #0f172a;
  color: #ffffff;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.15s ease, opacity 0.15s ease;
}

.secondary-btn:hover {
  transform: translateY(-1px);
  opacity: 0.96;
}

.hero-status {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  flex-wrap: wrap;
  margin-top: 1rem;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.7rem 0.95rem;
  border-radius: 999px;
  font-size: 0.9rem;
  font-weight: 700;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #334155;
}

.status-pill.online {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.2);
  color: #047857;
}

.status-pill.connecting {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.2);
  color: #b45309;
}

.status-pill.idle {
  background: rgba(148, 163, 184, 0.12);
  border-color: rgba(148, 163, 184, 0.2);
  color: #475569;
}

.status-pill.events {
  background: rgba(59, 130, 246, 0.08);
  border-color: rgba(59, 130, 246, 0.14);
  color: #1d4ed8;
}

.status-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: currentColor;
  opacity: 0.9;
}

.monitoring-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(340px, 0.95fr);
  gap: 1.5rem;
  min-height: 0;
}

.glass-card {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 28px;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
  backdrop-filter: blur(12px);
}

.video-card,
.events-card {
  padding: 1.35rem;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.card-label {
  font-size: 0.8rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #94a3b8;
  margin-bottom: 0.35rem;
}

.card-title {
  margin: 0;
  color: #0f172a;
  font-size: 1.25rem;
  font-weight: 800;
}

.camera-meta {
  display: flex;
  justify-content: flex-end;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.55rem 0.8rem;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #475569;
  font-size: 0.82rem;
  font-weight: 700;
  word-break: break-all;
}

.video-shell {
  position: relative;
  flex: 1;
  min-height: 480px;
  overflow: hidden;
  border-radius: 24px;
  background:
    radial-gradient(circle at top, rgba(59, 130, 246, 0.08), transparent 30%),
    #0f172a;
  display: flex;
  align-items: center;
  justify-content: center;
}

.live-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.video-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 2rem;
  color: #cbd5e1;
}

.placeholder-icon-wrap {
  width: 92px;
  height: 92px;
  border-radius: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.06);
  margin-bottom: 1rem;
}

.placeholder-icon {
  font-size: 2.8rem;
}

.placeholder-title {
  font-size: 1.1rem;
  font-weight: 800;
  color: #f8fafc;
  margin-bottom: 0.5rem;
}

.placeholder-text {
  font-size: 0.95rem;
  line-height: 1.55;
  color: #94a3b8;
  max-width: 320px;
}

.video-overlay {
  position: absolute;
  top: 1rem;
  left: 1rem;
}

.overlay-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 0.8rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #f8fafc;
  font-size: 0.8rem;
  font-weight: 800;
  backdrop-filter: blur(12px);
}

.overlay-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #f59e0b;
  box-shadow: 0 0 0 6px rgba(245, 158, 11, 0.14);
}

.overlay-dot.active {
  background: #10b981;
  box-shadow: 0 0 0 6px rgba(16, 185, 129, 0.14);
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  overflow-y: auto;
  min-height: 0;
  padding-right: 0.25rem;
}

.event-item {
  display: flex;
  gap: 0.9rem;
  align-items: flex-start;
  padding: 1rem;
  border-radius: 22px;
  border: 1px solid #eef2f7;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.event-item:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}

.event-item.success {
  border-left: 4px solid #10b981;
}

.event-item.danger {
  border-left: 4px solid #ef4444;
}

.event-icon-wrap {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  font-size: 1.2rem;
}

.event-item.success .event-icon-wrap {
  color: #10b981;
}

.event-item.danger .event-icon-wrap {
  color: #ef4444;
}

.event-content {
  min-width: 0;
  flex: 1;
}

.event-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.35rem;
}

.event-status {
  font-size: 0.92rem;
  font-weight: 800;
  color: #0f172a;
}

.event-time {
  flex-shrink: 0;
  font-size: 0.78rem;
  color: #94a3b8;
  font-weight: 700;
}

.event-message {
  color: #475569;
  line-height: 1.5;
  word-break: break-word;
}

.empty-state {
  display: flex;
  min-height: 260px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #94a3b8;
  padding: 2rem 1rem;
}

.empty-icon-wrap {
  width: 82px;
  height: 82px;
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  margin-bottom: 1rem;
}

.empty-icon {
  font-size: 2rem;
}

.empty-title {
  font-size: 1rem;
  font-weight: 800;
  color: #334155;
  margin-bottom: 0.4rem;
}

.empty-text {
  max-width: 260px;
  line-height: 1.55;
}

@media (max-width: 1200px) {
  .monitoring-hero,
  .monitoring-grid {
    grid-template-columns: 1fr;
  }

  .hero-actions,
  .hero-status {
    justify-content: flex-start;
  }

  .camera-select {
    min-width: 100%;
  }
}

@media (max-width: 768px) {
  .monitoring-hero,
  .video-card,
  .events-card {
    padding: 1rem;
    border-radius: 22px;
  }

  .hero-title {
    font-size: 1.5rem;
  }

  .video-shell {
    min-height: 320px;
    border-radius: 18px;
  }

  .card-head,
  .event-top {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>