<template>
  <div class="page-container">
    <div class="header-actions">
      <div>
        <h1 class="page-title">Камеры и Турникеты</h1>
        <p class="page-subtitle">Управление точками прохода и настройка направлений (Вход/Выход/Внутри).</p>
      </div>
      <button v-if="canManageCameras" class="btn-primary" @click="openNewDialog">
        <i class="pi pi-plus"></i> Добавить
      </button>
    </div>

    <div class="filters-bar">
      <div class="search-box">
        <i class="pi pi-search"></i>
        <input 
          type="text" 
          v-model="searchQuery" 
          placeholder="Поиск по названию или IP..." 
        />
      </div>

      <select v-model="selectedDirection" class="filter-select">
        <option value="all">Все направления</option>
        <option value="in">Вход</option>
        <option value="out">Выход</option>
        <option value="both">Двусторонняя</option>
        <option value="internal">Внутренняя</option>
      </select>

      <select v-model="selectedStatus" class="filter-select">
        <option value="all">Все статусы</option>
        <option value="active">Только в сети</option>
        <option value="offline">Отключены</option>
      </select>
    </div>

    <div class="cards-grid">
      <div v-for="cam in filteredCameras" :key="cam.id" class="camera-card" :class="{ 'offline-card': !cam.is_active }">
        <div class="card-header">
          <div class="status-indicator">
            <span class="status-dot" :class="cam.is_active ? 'online' : 'offline'"></span>
            <span class="status-text">{{ cam.is_active ? 'В сети' : 'Отключена' }}</span>
          </div>
          <div class="card-actions">
            <button v-if="cam.is_active" class="btn-icon success" @click="openVideoDialog(cam)" title="Смотреть трансляцию">
              <i class="pi pi-eye"></i>
            </button>
            <button v-if="canManageCameras" class="btn-icon warning" @click="openEditDialog(cam)" title="Редактировать">
              <i class="pi pi-pencil"></i>
            </button>
            <button v-if="canManageCameras" class="btn-icon danger" @click="confirmDelete(cam.id)" title="Удалить">
              <i class="pi pi-trash"></i>
            </button>
          </div>
        </div>

        <div class="card-body">
          <div class="cam-icon-wrapper" :class="cam.is_active ? 'active-icon' : 'disabled-icon'">
            <i class="pi pi-video"></i>
          </div>
          
          <h3 class="cam-name">{{ cam.name }}</h3>
          <div class="cam-ip">
            <i class="pi pi-link"></i> {{ cam.ip_address }}
          </div>
          
          <div class="cam-direction">
            <span v-if="cam.direction === 'in'" class="dir-badge in">
              <i class="pi pi-sign-in"></i> Вход в зону
            </span>
            <span v-else-if="cam.direction === 'out'" class="dir-badge out">
              <i class="pi pi-sign-out"></i> Выход из зоны
            </span>
            <span v-else-if="cam.direction === 'both'" class="dir-badge both">
              <i class="pi pi-arrows-h"></i> Двусторонняя
            </span>
            <span v-else class="dir-badge internal">
              <i class="pi pi-eye"></i> Внутренняя
            </span>
          </div>
        </div>
      </div>

      <div v-if="filteredCameras.length === 0" class="empty-state">
        <i class="pi pi-video empty-icon"></i>
        <h3>Камеры не найдены</h3>
        <p>По вашему запросу нет совпадений или камеры еще не добавлены.</p>
      </div>
    </div>

    <div v-if="displayDialog" class="modal-overlay" @click.self="closeDialog">
      <div class="modal-content">
        <div class="modal-header">
          <h2>{{ isEditMode ? 'Редактировать точку прохода' : 'Новая точка прохода' }}</h2>
          <button class="btn-icon close-btn" @click="closeDialog">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="form-group full-width">
          <label>Название зоны / камеры <span class="required">*</span></label>
          <input type="text" v-model="cameraForm.name" class="form-input" placeholder="Например: Опенспейс (Продажи)" />
        </div>

        <div class="form-grid">
          <div class="form-group">
            <label>IP или RTSP адрес <span class="required">*</span></label>
            <input type="text" v-model="cameraForm.ip_address" class="form-input" placeholder="rtsp://admin:123@..." />
          </div>

          <div class="form-group">
            <label>Направление движения <span class="required">*</span></label>
            <select v-model="cameraForm.direction" class="form-input">
              <option value="in">Вход (Приход на работу)</option>
              <option value="out">Выход (Уход с работы)</option>
              <option value="both">Двусторонняя (Вход и Выход)</option>
              <option value="internal">Внутренняя (Наблюдение внутри зоны)</option>
            </select>
          </div>
        </div>

        <div class="form-group checkbox-group">
          <input type="checkbox" id="isActive" v-model="cameraForm.is_active" />
          <label for="isActive">Камера активна (Включить обработку потока)</label>
        </div>

        <div class="modal-actions">
          <button class="btn-text" @click="closeDialog">Отмена</button>
          <button class="btn-primary" @click="saveCamera">Сохранить</button>
        </div>
      </div>
    </div>

    <div v-if="displayVideoDialog" class="modal-overlay" @click.self="closeVideoDialog">
      <div class="modal-content video-modal">
        <div class="video-header">
          <h2>Трансляция: {{ selectedCamera?.name }}</h2>
          <button class="btn-icon close-btn" @click="closeVideoDialog">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="video-container">
          <img v-if="currentFrame" :src="currentFrame" alt="Live stream" class="live-video" />

          <div v-else-if="videoError" class="video-placeholder video-error">
            <i class="pi pi-exclamation-triangle"></i>
            <p>{{ videoError }}</p>
          </div>

          <div v-else class="video-placeholder">
            <i class="pi pi-spin pi-spinner"></i>
            <p>{{ isVideoLoading ? 'Подключение к потоку...' : 'Ожидание видео...' }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { camerasApi } from '../api/cameras'
import { buildWsUrl } from '../api/client'
import { useAuth } from '../services/auth'

const auth = useAuth()
const canManageCameras = computed(() => auth.hasAnyRole('super_admin', 'tech_hr'))

const cameras = ref([])
const displayDialog = ref(false)
const displayVideoDialog = ref(false)
const isEditMode = ref(false)
const selectedCamera = ref(null)

// === НОВЫЕ ПЕРЕМЕННЫЕ ДЛЯ ФИЛЬТРАЦИИ ===
const searchQuery = ref('')
const selectedDirection = ref('all')
const selectedStatus = ref('all')

const cameraForm = ref({
  id: null,
  name: '',
  ip_address: '',
  direction: 'internal',
  is_active: true
})

const currentFrame = ref(null)
const isVideoLoading = ref(false)
const videoError = ref('')

let ws = null
let lastBlobUrl = null
let connectionTimer = null
let wsSession = 0
let manualVideoClose = false

const clearConnectionTimer = () => {
  if (connectionTimer) {
    clearTimeout(connectionTimer)
    connectionTimer = null
  }
}

const revokeLastBlob = () => {
  if (lastBlobUrl) {
    URL.revokeObjectURL(lastBlobUrl)
    lastBlobUrl = null
  }
}

const resetVideoState = () => {
  currentFrame.value = null
  isVideoLoading.value = false
  videoError.value = ''
}

const cleanupVideoSocket = ({ closeSocket = true } = {}) => {
  clearConnectionTimer()
  if (ws) {
    const socket = ws
    ws = null
    socket.onopen = null
    socket.onmessage = null
    socket.onerror = null
    socket.onclose = null
    if (closeSocket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) {
      try { socket.close(1000, 'client_closed') } catch (error) {}
    }
  }
  revokeLastBlob()
}

const loadData = async () => {
  try {
    const response = await camerasApi.getCameras()
    cameras.value = response.data
  } catch (error) {
    console.error('Ошибка загрузки камер', error)
  }
}

// === ВЫЧИСЛЯЕМОЕ СВОЙСТВО ДЛЯ ФИЛЬТРАЦИИ КАРТОЧЕК ===
const filteredCameras = computed(() => {
  return cameras.value.filter(cam => {
    // 1. Поиск по имени или IP
    const query = searchQuery.value.toLowerCase()
    const matchesSearch = cam.name.toLowerCase().includes(query) || 
                          cam.ip_address.toLowerCase().includes(query)
    
    // 2. Фильтр по направлению
    const matchesDirection = selectedDirection.value === 'all' || 
                             cam.direction === selectedDirection.value
    
    // 3. Фильтр по статусу
    const matchesStatus = selectedStatus.value === 'all' ||
                          (selectedStatus.value === 'active' && cam.is_active) ||
                          (selectedStatus.value === 'offline' && !cam.is_active)
                          
    return matchesSearch && matchesDirection && matchesStatus
  })
})

const openNewDialog = () => {
  if (!canManageCameras.value) return
  isEditMode.value = false
  cameraForm.value = { id: null, name: '', ip_address: '', direction: 'internal', is_active: true }
  displayDialog.value = true
}

const openEditDialog = (camera) => {
  if (!canManageCameras.value) return
  isEditMode.value = true
  cameraForm.value = { ...camera, direction: camera.direction || 'internal' }
  displayDialog.value = true
}

const closeDialog = () => {
  displayDialog.value = false
}

const saveCamera = async () => {
  if (!canManageCameras.value) return
  if (!cameraForm.value.name || !cameraForm.value.ip_address) {
    alert('Заполните название и адрес камеры')
    return
  }

  try {
    const payload = {
      name: cameraForm.value.name,
      ip_address: cameraForm.value.ip_address,
      direction: cameraForm.value.direction,
      is_active: cameraForm.value.is_active
    }

    if (isEditMode.value) {
      await camerasApi.updateCamera(cameraForm.value.id, payload)
    } else {
      await camerasApi.createCamera(payload)
    }

    closeDialog()
    await loadData()
  } catch (error) {
    console.error('Ошибка при сохранении камеры:', error)
    const errorMsg = error.response?.data?.detail || error.message || 'Неизвестная ошибка сервера'
    alert(`Реальная ошибка сервера:\n\n${JSON.stringify(errorMsg, null, 2)}`)
  }
}

const confirmDelete = async (id) => {
  if (!canManageCameras.value) return
  if (confirm('Точно удалить камеру из системы?')) {
    try {
      await camerasApi.deleteCamera(id)
      await loadData()
    } catch (error) {
      console.error('Ошибка удаления камеры', error)
    }
  }
}

const openVideoDialog = (camera) => {
  manualVideoClose = false
  cleanupVideoSocket()
  resetVideoState()

  selectedCamera.value = camera
  displayVideoDialog.value = true
  isVideoLoading.value = true

  const currentSession = ++wsSession
  const socket = new WebSocket(buildWsUrl(`/ws/video/${camera.id}`))

  ws = socket
  socket.binaryType = 'blob'

  connectionTimer = setTimeout(() => {
    if (ws !== socket || currentSession !== wsSession) return
    videoError.value = 'Не удалось подключиться к потоку'
    isVideoLoading.value = false
    cleanupVideoSocket()
  }, 5000)

  socket.onopen = () => {
    if (ws !== socket || currentSession !== wsSession) return
  }

  socket.onmessage = (event) => {
    if (ws !== socket || currentSession !== wsSession) return
    clearConnectionTimer()
    isVideoLoading.value = false
    videoError.value = ''
    revokeLastBlob()
    lastBlobUrl = URL.createObjectURL(event.data)
    currentFrame.value = lastBlobUrl
  }

  socket.onerror = (event) => {
    if (ws !== socket || currentSession !== wsSession) return
    clearConnectionTimer()
    isVideoLoading.value = false
    videoError.value = 'Ошибка подключения к потоку'
  }

  socket.onclose = (event) => {
    if (ws !== socket || currentSession !== wsSession) return
    ws = null
    clearConnectionTimer()
    revokeLastBlob()
    currentFrame.value = null
    isVideoLoading.value = false
    if (displayVideoDialog.value && !manualVideoClose) {
      videoError.value = event.reason ? `Поток закрыт: ${event.reason}` : `Поток закрыт (код ${event.code})`
    }
  }
}

const closeVideoDialog = () => {
  manualVideoClose = true
  displayVideoDialog.value = false
  selectedCamera.value = null
  resetVideoState()
  cleanupVideoSocket()
}

onMounted(() => {
  loadData()
})

onBeforeUnmount(() => {
  manualVideoClose = true
  cleanupVideoSocket()
})
</script>

<style scoped>
.page-container { background: transparent; height: 100%; display: flex; flex-direction: column; gap: 1.5rem; }
.header-actions { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem; }
.page-title { font-size: 1.75rem; font-weight: 700; color: #0f172a; margin: 0; }
.page-subtitle { margin: 0.35rem 0 0; color: #64748b; font-size: 0.95rem; }

/* === СТИЛИ ПАНЕЛИ ФИЛЬТРОВ === */
.filters-bar { display: flex; gap: 1rem; flex-wrap: wrap; background: #ffffff; padding: 1rem; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.search-box { position: relative; flex: 1; min-width: 250px; }
.search-box i { position: absolute; left: 1rem; top: 50%; transform: translateY(-50%); color: #94a3b8; }
.search-box input { width: 100%; padding: 0.75rem 1rem 0.75rem 2.5rem; border-radius: 8px; border: 1px solid #cbd5e1; background: #f8fafc; font-size: 0.95rem; outline: none; transition: 0.2s; }
.search-box input:focus { border-color: #3b82f6; background: #ffffff; }
.filter-select { padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid #cbd5e1; background: #f8fafc; color: #334155; font-size: 0.95rem; outline: none; min-width: 180px; cursor: pointer; }

.cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.5rem; }
.camera-card { background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; padding: 1.5rem; transition: transform 0.2s, box-shadow 0.2s; position: relative; display: flex; flex-direction: column; }
.camera-card:hover { transform: translateY(-3px); box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08); }
.offline-card { background: #f8fafc; border-color: #cbd5e1; }

.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem; }
.status-indicator { display: flex; align-items: center; gap: 0.5rem; background: #f1f5f9; padding: 0.3rem 0.8rem; border-radius: 999px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-dot.online { background: #10b981; box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2); animation: pulse 2s infinite; }
.status-dot.offline { background: #94a3b8; }
.status-text { font-size: 0.75rem; font-weight: 700; color: #334155; text-transform: uppercase; letter-spacing: 0.05em; }

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
  70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
  100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

.card-actions { display: flex; gap: 0.25rem; }

.card-body { display: flex; flex-direction: column; align-items: center; text-align: center; }
.cam-icon-wrapper { width: 70px; height: 70px; border-radius: 20px; display: flex; align-items: center; justify-content: center; font-size: 2rem; margin-bottom: 1rem; transition: 0.3s; }
.cam-icon-wrapper.active-icon { background: linear-gradient(135deg, #3b82f6, #8b5cf6); color: white; box-shadow: 0 8px 16px rgba(59, 130, 246, 0.25); }
.cam-icon-wrapper.disabled-icon { background: #e2e8f0; color: #94a3b8; }

.cam-name { margin: 0 0 0.5rem 0; color: #0f172a; font-size: 1.15rem; font-weight: 700; }
.cam-ip { color: #64748b; font-size: 0.85rem; font-family: monospace; background: #f8fafc; padding: 0.3rem 0.6rem; border-radius: 6px; border: 1px solid #e2e8f0; margin-bottom: 1.25rem; display: inline-flex; align-items: center; gap: 0.4rem; }

.cam-direction { width: 100%; display: flex; justify-content: center; }
.dir-badge { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.85rem; font-weight: 600; width: 100%; justify-content: center; }
.dir-badge.in { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
.dir-badge.out { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
.dir-badge.both { background: #e0f2fe; color: #1e40af; border: 1px solid #bfdbfe; }
.dir-badge.internal { background: #f3e8ff; color: #5b21b6; border: 1px solid #e9d5ff; }

.empty-state { grid-column: 1 / -1; display: flex; flex-direction: column; align-items: center; padding: 4rem 2rem; color: #94a3b8; background: #ffffff; border-radius: 16px; border: 1px dashed #cbd5e1; }
.empty-icon { font-size: 3rem; margin-bottom: 1rem; color: #cbd5e1; }
.empty-state h3 { color: #334155; margin: 0 0 0.5rem 0; }

.btn-primary, .btn-text { border: none; padding: 0.65rem 1.2rem; border-radius: 8px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 0.5rem; transition: 0.2s; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:hover { background: #2563eb; }
.btn-text { background: transparent; color: #64748b; }
.btn-text:hover { background: #f1f5f9; color: #0f172a; }

.btn-icon { background: transparent; border: none; cursor: pointer; width: 36px; height: 36px; border-radius: 8px; color: #64748b; display: flex; align-items: center; justify-content: center; transition: 0.2s; }
.btn-icon:hover { background: #f1f5f9; color: #0f172a; }
.btn-icon.success:hover { background: #dcfce7; color: #10b981; }
.btn-icon.warning:hover { background: #fef3c7; color: #f59e0b; }
.btn-icon.danger:hover { background: #fee2e2; color: #ef4444; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: white; padding: 2rem; border-radius: 16px; width: 100%; max-width: 550px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25); }
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.modal-header h2 { margin: 0; font-size: 1.3rem; color: #0f172a; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
.form-group { display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 1.25rem; }
.form-group.full-width { grid-column: 1 / -1; }
.form-group label { font-size: 0.85rem; font-weight: 600; color: #475569; }
.required { color: #ef4444; }

.form-input { 
  width: 100%; 
  box-sizing: border-box; 
  padding: 0.75rem 1rem; 
  border: 1px solid #cbd5e1; 
  border-radius: 8px; 
  font-size: 0.95rem; 
  background: #f8fafc; 
  outline: none; 
}
.form-input:focus { border-color: #3b82f6; background: #ffffff; }

.checkbox-group { flex-direction: row; align-items: center; margin-top: 0.5rem; }
.checkbox-group input { width: 18px; height: 18px; cursor: pointer; }
.checkbox-group label { cursor: pointer; margin: 0; font-size: 0.95rem; font-weight: 500; }

.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 2rem; border-top: 1px solid #e2e8f0; padding-top: 1.5rem; }

.video-modal { max-width: 800px; padding: 1.5rem; }
.video-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.video-header h2 { margin: 0; font-size: 1.2rem; color: #0f172a; }
.video-container { width: 100%; aspect-ratio: 16 / 9; background-color: #0f172a; border-radius: 12px; overflow: hidden; display: flex; align-items: center; justify-content: center; }
.live-video { width: 100%; height: 100%; object-fit: contain; }
.video-placeholder { color: #cbd5e1; display: flex; flex-direction: column; align-items: center; gap: 1rem; }
.video-error { color: #fca5a5; }

@media (max-width: 768px) {
  .form-grid { grid-template-columns: 1fr; }
  .filters-bar { flex-direction: column; }
  .search-box, .filter-select { width: 100%; }
}
</style>