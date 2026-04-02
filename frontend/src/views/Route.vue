<template>
  <div class="monitoring-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">Мониторинг проходной</h1>
        <p class="page-subtitle">Онлайн-наблюдение и выдача гостевых пропусков в реальном времени.</p>
      </div>
      <div class="header-controls">
        <div class="select-wrapper">
          <select v-model="selectedCameraId" @change="startVideoFeed" class="form-input camera-select">
            <option value="" disabled>Выберите камеру для просмотра...</option>
            <option v-for="cam in activeCameras" :key="cam.id" :value="cam.id">
              {{ cam.name }}
            </option>
          </select>
        </div>
        
        <button class="btn-primary" @click="openGuestDialog" :disabled="!selectedCameraId">
          <i class="pi pi-id-card"></i> Выдать пропуск
        </button>
      </div>
    </div>

    <div class="monitoring-layout">
      
      <div class="video-section">
        <div class="video-container">
          <img v-if="currentFrame" :src="currentFrame" alt="Live stream" class="live-video" />
          
          <div v-else class="video-placeholder">
            <i class="pi" :class="isVideoLoading ? 'pi-spin pi-spinner' : 'pi-camera'"></i>
            <p>{{ isVideoLoading ? 'Подключение к потоку...' : 'Выберите камеру для начала мониторинга' }}</p>
          </div>

          <div class="rec-indicator" v-if="currentFrame">
             <span class="rec-dot"></span> LIVE
          </div>
        </div>
      </div>

      <div class="log-section">
        <div class="log-header">
          <h3><i class="pi pi-list"></i> Журнал событий</h3>
          <span class="log-badge" v-if="selectedCameraId">Только текущая камера</span>
        </div>
        
        <div class="log-list" v-if="logs.length > 0">
          <div v-for="log in logs" :key="log.id" class="log-item" :class="log.status">
            <div class="log-icon">
              <i class="pi" :class="log.status === 'granted' ? 'pi-check-circle' : 'pi-exclamation-triangle'"></i>
            </div>
            <div class="log-content">
              <div class="log-name" :class="{'unknown': log.status === 'denied'}">
                 {{ log.status === 'granted' ? log.employee_name : 'Неизвестное лицо' }}
              </div>
              <div class="log-camera">{{ log.camera_name }}</div>
            </div>
            <div class="log-time">{{ formatTime(log.timestamp) }}</div>
          </div>
        </div>
        
        <div v-else class="empty-log">
          <i class="pi pi-history"></i>
          <p>Ожидание проходов...</p>
        </div>
      </div>
    </div>

    <div v-if="displayGuestDialog" class="modal-overlay" @click.self="closeGuestDialog">
      <div class="modal-content wide-modal">
        <div class="modal-header">
          <h2>Оформление гостевого пропуска</h2>
          <button class="btn-icon close-btn" @click="closeGuestDialog">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="modal-body-split">
          <div class="photo-column">
            <div class="avatar-preview">
              <img v-if="photoPreview" :src="photoPreview" class="avatar-img large" />
              <div v-else class="avatar-placeholder large">
                <i class="pi pi-camera"></i>
              </div>
            </div>

            <div class="capture-controls">
              <button class="btn-primary full-width-btn" @click="takeSnapshot" :disabled="isTakingSnapshot">
                <i class="pi" :class="isTakingSnapshot ? 'pi-spin pi-spinner' : 'pi-camera'"></i> 
                Сделать снимок (Live)
              </button>
              <p class="capture-hint">Убедитесь, что лицо гостя видно в камере.</p>
            </div>
          </div>

          <div class="form-column">
            <div class="form-grid">
              <div class="form-group">
                <label>Фамилия <span class="required">*</span></label>
                <input v-model="guestForm.last_name" type="text" class="form-input" />
              </div>
              
              <div class="form-group">
                <label>Имя <span class="required">*</span></label>
                <input v-model="guestForm.first_name" type="text" class="form-input" />
              </div>

              <div class="form-group">
                <label>Отчество</label>
                <input v-model="guestForm.middle_name" type="text" class="form-input" />
              </div>

              <div class="form-group">
                <label>Срок действия до <span class="required">*</span></label>
                <input v-model="guestForm.valid_until" type="datetime-local" class="form-input" />
              </div>

              <div class="form-group full-width">
                <label>Цель визита / К кому направляется</label>
                <input v-model="guestForm.purpose" type="text" class="form-input" placeholder="Например: Встреча в переговорной" />
              </div>
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-text" @click="closeGuestDialog">Отмена</button>
          <button class="btn-primary" @click="saveGuest">Выдать пропуск</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { camerasApi } from '../api/cameras'
import { analyticsApi } from '../api/analytics'
import { guestsApi } from '../api/guests'

const cameras = ref([])
const selectedCameraId = ref('')

const currentFrame = ref(null)
const isVideoLoading = ref(false)

const logs = ref([])
let logInterval = null

let ws = null

const displayGuestDialog = ref(false)
const isTakingSnapshot = ref(false)
const photoPreview = ref(null)
const guestForm = ref({
  last_name: '', first_name: '', middle_name: '', purpose: '', valid_until: '', photoFile: null
})

const activeCameras = computed(() => cameras.value.filter(c => c.is_active))

const loadCameras = async () => {
  try {
    const res = await camerasApi.getCameras()
    cameras.value = res.data
  } catch (error) {
    console.error('Ошибка загрузки камер:', error)
  }
}

const fetchLogs = async () => {
  try {
    const res = await analyticsApi.getAccessLogs(30)
    
    if (selectedCameraId.value) {
      const selectedCam = cameras.value.find(c => c.id === selectedCameraId.value)
      if (selectedCam) {
        logs.value = res.data.filter(l => l.camera_name === selectedCam.name).slice(0, 15)
        return
      }
    }
    logs.value = res.data.slice(0, 15)
  } catch (error) {
    console.error('Ошибка загрузки логов:', error)
  }
}

const formatTime = (dateString) => {
  const d = new Date(dateString + 'Z')
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const cleanupVideoSocket = () => {
  if (ws) {
    ws.onmessage = null
    ws.onerror = null
    ws.close()
    ws = null
  }
  if (currentFrame.value) {
    URL.revokeObjectURL(currentFrame.value)
    currentFrame.value = null
  }
}

const startVideoFeed = () => {
  cleanupVideoSocket()
  fetchLogs() 

  if (!selectedCameraId.value) return
  
  isVideoLoading.value = true
  const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const apiHost = `${window.location.hostname}:8000`
  ws = new WebSocket(`${wsProtocol}://${apiHost}/ws/video/${selectedCameraId.value}`)
  
  ws.binaryType = 'blob'
  
  ws.onmessage = (event) => {
    isVideoLoading.value = false
    if (currentFrame.value) {
      URL.revokeObjectURL(currentFrame.value)
    }
    currentFrame.value = URL.createObjectURL(event.data)
  }
  
  ws.onerror = () => {
    isVideoLoading.value = false
    console.error('Ошибка видеопотока')
  }
}

const openGuestDialog = () => {
  photoPreview.value = null
  
  const today = new Date()
  today.setHours(23, 59, 0, 0)
  const tzOffset = (new Date()).getTimezoneOffset() * 60000;
  const localISOTime = (new Date(today - tzOffset)).toISOString().slice(0, 16);

  guestForm.value = { 
    last_name: '', first_name: '', middle_name: '', purpose: '',
    valid_until: localISOTime,
    photoFile: null 
  }
  displayGuestDialog.value = true
}

const closeGuestDialog = () => {
  displayGuestDialog.value = false
  if (photoPreview.value) URL.revokeObjectURL(photoPreview.value)
}

const takeSnapshot = async () => {
  if (!selectedCameraId.value) return
  isTakingSnapshot.value = true
  try {
    const res = await camerasApi.getSnapshot(selectedCameraId.value)
    const blob = res.data
    const file = new File([blob], "snapshot.jpg", { type: "image/jpeg" })
    guestForm.value.photoFile = file
    
    if (photoPreview.value) URL.revokeObjectURL(photoPreview.value)
    photoPreview.value = URL.createObjectURL(blob)
  } catch (error) {
    alert('Не удалось сделать снимок. Возможно, камера временно недоступна.')
  } finally {
    isTakingSnapshot.value = false
  }
}

const saveGuest = async () => {
  if (!guestForm.value.last_name || !guestForm.value.first_name || !guestForm.value.valid_until) {
    alert('Заполните обязательные поля (Фамилия, Имя, Срок действия)')
    return
  }
  if (!guestForm.value.photoFile) {
    alert('Сделайте снимок с камеры!')
    return
  }

  try {
    const formData = new FormData()
    formData.append('last_name', guestForm.value.last_name)
    formData.append('first_name', guestForm.value.first_name)
    if (guestForm.value.middle_name) formData.append('middle_name', guestForm.value.middle_name)
    if (guestForm.value.purpose) formData.append('purpose', guestForm.value.purpose)
    
    formData.append('valid_until', guestForm.value.valid_until)
    formData.append('photo', guestForm.value.photoFile)

    await guestsApi.createGuest(formData)
    closeGuestDialog()
    alert('Гостевой пропуск успешно выдан! Теперь человек может пройти через турникет.')
  } catch (error) {
    const errorMsg = error.response?.data?.detail || 'Ошибка сохранения гостя'
    alert(errorMsg)
  }
}

onMounted(() => {
  loadCameras()
  fetchLogs()
  logInterval = setInterval(fetchLogs, 2000)
})

onBeforeUnmount(() => {
  clearInterval(logInterval)
  cleanupVideoSocket()
})
</script>

<style scoped>
.monitoring-page { display: flex; flex-direction: column; gap: 1.5rem; height: 100%; }

.page-header { display: flex; justify-content: space-between; align-items: flex-end; }
.page-title { font-size: 1.75rem; font-weight: 700; color: #0f172a; margin: 0; }
.page-subtitle { margin: 0.35rem 0 0; color: #64748b; font-size: 0.95rem; }

.header-controls { display: flex; gap: 1rem; align-items: center; }
.select-wrapper { position: relative;}
.select-icon { position: absolute; left: 1rem; top: 50%; transform: translateY(-50%); color: #64748b; }
.camera-select { padding: 0.65rem 1rem 0.65rem 2.5rem; min-width: 250px; border-radius: 8px; border: 1px solid #cbd5e1; font-size: 0.95rem; background: #ffffff; outline: none; cursor: pointer; }
.camera-select:focus { border-color: #3b82f6; }

.monitoring-layout { display: grid; grid-template-columns: 2.2fr 1fr; gap: 1.5rem; flex: 1; align-items: flex-start; }

.video-section { background: #1e293b; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.1); position: relative; }
.video-container { width: 100%; aspect-ratio: 16 / 9; display: flex; align-items: center; justify-content: center; position: relative; }
.live-video { width: 100%; height: 100%; object-fit: contain; }
.video-placeholder { color: #64748b; display: flex; flex-direction: column; align-items: center; gap: 1rem; font-size: 1.1rem; }
.video-placeholder i { font-size: 3rem; color: #475569; }

.rec-indicator { position: absolute; top: 1.5rem; left: 1.5rem; background: rgba(0,0,0,0.6); color: white; padding: 0.4rem 0.8rem; border-radius: 6px; font-size: 0.8rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem; letter-spacing: 1px; backdrop-filter: blur(4px); }
.rec-dot { width: 8px; height: 8px; background: #ef4444; border-radius: 50%; box-shadow: 0 0 8px #ef4444; animation: blink 1.5s infinite; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

.log-section { background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; height: 90%; max-height: calc(100vh - 180px); }
.log-header { padding: 1.2rem 1.5rem; border-bottom: 1px solid #f1f5f9; display: flex; justify-content: space-between; align-items: center; }
.log-header h3 { margin: 0; font-size: 1.1rem; color: #0f172a; display: flex; align-items: center; gap: 0.5rem; }
.log-badge { font-size: 0.7rem; background: #e0f2fe; color: #1d4ed8; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600; }

.log-list { padding: 1rem; overflow-y: auto; display: flex; flex-direction: column; gap: 0.75rem; flex: 1; }
.log-list::-webkit-scrollbar { width: 6px; }
.log-list::-webkit-scrollbar-track { background: #f1f5f9; }
.log-list::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }

.log-item { display: flex; align-items: center; gap: 1rem; padding: 0.85rem 1rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; }
.log-item.denied { background: #fef2f2; border-color: #fecaca; }

.log-icon { font-size: 1.5rem; }
.log-item.granted .log-icon { color: #10b981; }
.log-item.denied .log-icon { color: #ef4444; }

.log-content { flex: 1; display: flex; flex-direction: column; gap: 0.2rem; }
.log-name { font-weight: 700; color: #0f172a; font-size: 0.95rem; }
.log-name.unknown { color: #b91c1c; }
.log-camera { color: #64748b; font-size: 0.8rem; }
.log-time { font-size: 0.85rem; font-weight: 700; color: #94a3b8; }

.empty-log { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 3rem 1rem; color: #94a3b8; text-align: center; flex: 1; }
.empty-log i { font-size: 2.5rem; margin-bottom: 1rem; color: #cbd5e1; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: white; padding: 2rem; border-radius: 16px; width: 100%; max-height: 90vh; overflow-y: auto; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25); }
.wide-modal { max-width: 850px; }

.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.modal-header h2 { margin: 0; font-size: 1.3rem; color: #0f172a; }

.modal-body-split { display: flex; gap: 2rem; align-items: flex-start; }
.photo-column { width: 280px; flex-shrink: 0; display: flex; flex-direction: column; gap: 1.5rem; background: #f8fafc; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; }
.form-column { flex: 1; }

.avatar-preview { display: flex; justify-content: center; margin-bottom: 0.5rem; }
.avatar-placeholder { width: 130px; height: 130px; border-radius: 50%; background: #e2e8f0; color: #94a3b8; display: flex; align-items: center; justify-content: center; font-size: 3.5rem; }
.avatar-img { width: 130px; height: 130px; border-radius: 50%; object-fit: cover; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }

.capture-controls { display: flex; flex-direction: column; gap: 0.75rem; text-align: center; }
.capture-hint { font-size: 0.8rem; color: #64748b; margin: 0; }
.full-width-btn { width: 100%; justify-content: center; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
.form-group { display: flex; flex-direction: column; gap: 0.4rem; }
.form-group.full-width { grid-column: 1 / -1; }
.form-group label { font-size: 0.85rem; font-weight: 600; color: #475569; }
.required { color: #ef4444; }
.form-input { width: 100%; box-sizing: border-box; padding: 0.75rem 1rem; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 0.95rem; background: #ffffff; outline: none; }
.form-input:focus { border-color: #3b82f6; }
.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 2rem; border-top: 1px solid #e2e8f0; padding-top: 1.5rem; }

.btn-primary, .btn-text { border: none; padding: 0.65rem 1.2rem; border-radius: 8px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 0.5rem; transition: 0.2s; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-primary:disabled { background: #94a3b8; cursor: not-allowed; }
.btn-text { background: transparent; color: #64748b; }
.btn-text:hover { background: #f1f5f9; color: #0f172a; }
.btn-icon { background: transparent; border: none; cursor: pointer; width: 32px; height: 32px; border-radius: 6px; color: #64748b; display: flex; align-items: center; justify-content: center; }
.btn-icon:hover { background: #f1f5f9; color: #0f172a; }

@media (max-width: 1024px) {
  .monitoring-layout { grid-template-columns: 1fr; }
  .log-section { max-height: 400px; }
}
@media (max-width: 768px) {
  .header-controls { flex-direction: column; align-items: stretch; }
  .modal-body-split { flex-direction: column; }
  .photo-column { width: 100%; box-sizing: border-box; }
  .form-grid { grid-template-columns: 1fr; }
}
</style>