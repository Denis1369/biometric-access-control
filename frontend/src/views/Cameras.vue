<template>
  <div class="page-container">
    <div class="header-actions">
      <h1 class="page-title">Камеры</h1>
      <button class="btn-primary" @click="openNewDialog">
        <i class="pi pi-plus"></i> Добавить
      </button>
    </div>

    <DataTable :value="cameras" responsiveLayout="scroll" class="p-datatable-sm">
      <Column field="id" header="ID" sortable></Column>
      <Column field="name" header="Название"></Column>
      <Column field="ip_address" header="IP / RTSP Адрес"></Column>
      <Column header="Статус">
        <template #body="slotProps">
          <span :class="['status-badge', slotProps.data.is_active ? 'active' : 'inactive']">
            {{ slotProps.data.is_active ? 'В сети' : 'Отключена' }}
          </span>
        </template>
      </Column>
      <Column header="Действия">
        <template #body="slotProps">
          <div class="action-buttons">
            <button 
              v-if="slotProps.data.is_active" 
              class="btn-icon success" 
              @click="openVideoDialog(slotProps.data)"
              title="Смотреть трансляцию"
            >
              <i class="pi pi-eye"></i>
            </button>
            <button class="btn-icon warning" @click="openEditDialog(slotProps.data)" title="Редактировать">
              <i class="pi pi-pencil"></i>
            </button>
            <button class="btn-icon danger" @click="confirmDelete(slotProps.data.id)" title="Удалить">
              <i class="pi pi-trash"></i>
            </button>
          </div>
        </template>
      </Column>
    </DataTable>

    <div v-if="displayDialog" class="modal-overlay">
      <div class="modal-content">
        <h2>{{ isEditMode ? 'Редактировать камеру' : 'Новая камера' }}</h2>
        
        <div class="form-group">
          <label>Название зоны / камеры *</label>
          <input type="text" v-model="cameraForm.name" class="form-input" placeholder="Например: Главный вход" />
        </div>
        
        <div class="form-group">
          <label>IP или RTSP адрес *</label>
          <input type="text" v-model="cameraForm.ip_address" class="form-input" placeholder="rtsp://admin:123@192.168.1.10..." />
        </div>

        <div class="form-group checkbox-group">
          <input type="checkbox" id="isActive" v-model="cameraForm.is_active" />
          <label for="isActive">Камера активна</label>
        </div>

        <div class="modal-actions">
          <button class="btn-text" @click="closeDialog">Отмена</button>
          <button class="btn-primary" @click="saveCamera">Сохранить</button>
        </div>
      </div>
    </div>

    <div v-if="displayVideoDialog" class="modal-overlay">
      <div class="modal-content video-modal">
        <div class="video-header">
          <h2>Трансляция: {{ selectedCamera?.name }}</h2>
          <button class="btn-icon close-btn" @click="closeVideoDialog">
            <i class="pi pi-times"></i>
          </button>
        </div>
        
        <div class="video-container">
          <img v-if="currentFrame" :src="currentFrame" alt="Live stream" class="live-video" />
          <div v-else class="video-placeholder">
            <i class="pi pi-spin pi-spinner"></i>
            <p>Подключение к потоку...</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { camerasApi } from '../api/cameras'

const cameras = ref([])
const displayDialog = ref(false)
const displayVideoDialog = ref(false)
const isEditMode = ref(false)
const selectedCamera = ref(null)

const cameraForm = ref({
  id: null,
  name: '',
  ip_address: '',
  is_active: true
})

let ws = null
const currentFrame = ref(null)

const loadData = async () => {
  try {
    const response = await camerasApi.getCameras()
    cameras.value = response.data
  } catch (error) {}
}

const openNewDialog = () => {
  isEditMode.value = false
  cameraForm.value = { id: null, name: '', ip_address: '', is_active: true }
  displayDialog.value = true
}

const openEditDialog = (camera) => {
  isEditMode.value = true
  cameraForm.value = { ...camera }
  displayDialog.value = true
}

const closeDialog = () => {
  displayDialog.value = false
}

const saveCamera = async () => {
  if (!cameraForm.value.name || !cameraForm.value.ip_address) {
    alert('Заполните название и адрес камеры')
    return
  }

  try {
    const payload = {
      name: cameraForm.value.name,
      ip_address: cameraForm.value.ip_address,
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
    alert('Ошибка при сохранении. Возможно, такой адрес уже существует.')
  }
}

const confirmDelete = async (id) => {
  if (confirm('Точно удалить камеру из системы?')) {
    try {
      await camerasApi.deleteCamera(id)
      await loadData()
    } catch (error) {}
  }
}

const openVideoDialog = (camera) => {
  selectedCamera.value = camera
  displayVideoDialog.value = true
  currentFrame.value = null

  ws = new WebSocket(`ws://localhost:8000/ws/video/${camera.id}`)
  
  ws.onmessage = (event) => {
    currentFrame.value = `data:image/jpeg;base64,${event.data}`
  }

  ws.onerror = () => {
    alert('Ошибка подключения к потоку камеры')
    closeVideoDialog()
  }
}

const closeVideoDialog = () => {
  displayVideoDialog.value = false
  currentFrame.value = null
  selectedCamera.value = null
  
  if (ws) {
    ws.close()
    ws = null
  }
}

onMounted(() => {
  loadData()
})

onBeforeUnmount(() => {
  if (ws) {
    ws.close()
  }
})
</script>

<style scoped>
.page-container {
  background: #ffffff;
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.page-title {
  font-size: 1.25rem;
  color: #1e293b;
}

.btn-primary {
  background-color: #10b981;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
}

.btn-text {
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem 1rem;
  font-weight: 500;
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
}

.btn-icon {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 4px;
  font-size: 1rem;
}

.btn-icon.success { color: #10b981; }
.btn-icon.success:hover { background-color: #dcfce7; }

.btn-icon.warning { color: #f59e0b; }
.btn-icon.warning:hover { background-color: #fef3c7; }

.btn-icon.danger { color: #ef4444; }
.btn-icon.danger:hover { background-color: #fee2e2; }

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.status-badge.active { background: #dcfce7; color: #166534; }
.status-badge.inactive { background: #fee2e2; color: #991b1b; }

.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(15, 23, 42, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  width: 100%;
  max-width: 500px;
}

.video-modal {
  max-width: 700px;
  padding: 1.5rem;
}

.video-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.close-btn {
  color: #64748b;
}

.close-btn:hover {
  background-color: #f1f5f9;
}

.video-container {
  width: 100%;
  aspect-ratio: 4 / 3;
  background-color: #0f172a;
  border-radius: 6px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.live-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.video-placeholder {
  color: #cbd5e1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  color: #475569;
}

.form-input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  font-size: 1rem;
}

.checkbox-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 1.5rem;
}

.checkbox-group input {
  width: 1.25rem;
  height: 1.25rem;
}

.checkbox-group label {
  margin-bottom: 0;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 2rem;
}
</style>