<template>
  <div class="page-container">
    <div class="header-panel">
      <div>
        <h1 class="page-title">План здания</h1>
        <p class="page-subtitle">Выбор здания, этажа, загрузка плана и расстановка камер.</p>
      </div>

      <div class="top-buttons">
        <button class="btn-secondary" @click="openBuildingModal()">
          <i class="pi pi-building"></i> Новое здание
        </button>
        <button class="btn-secondary" @click="openFloorModal()" :disabled="!selectedBuildingId">
          <i class="pi pi-plus"></i> Новый этаж
        </button>
        <button class="btn-secondary" @click="openFloorModal(true)" :disabled="!selectedFloorId">
          <i class="pi pi-image"></i> План этажа
        </button>
      </div>
    </div>

    <div class="filters-row">
      <div class="filter-group wide">
        <label>Здание</label>
        <select v-model="selectedBuildingId" class="form-input">
          <option value="">Выберите здание...</option>
          <option v-for="building in buildings" :key="building.id" :value="String(building.id)">
            {{ building.name }}
          </option>
        </select>
      </div>

      <div class="filter-group wide">
        <label>Этаж</label>
        <select v-model="selectedFloorId" class="form-input" :disabled="!selectedBuildingId || floorsLoading">
          <option value="">Выберите этаж...</option>
          <option v-for="floor in floors" :key="floor.id" :value="String(floor.id)">
            {{ floor.name }} ({{ floor.floor_number }} этаж)
          </option>
        </select>
      </div>

      <div class="filter-group wide" v-if="!isEditMode">
        <label>Журнал</label>
        <select v-model="selectedEmployeeId" class="form-input">
          <option value="">Все сотрудники</option>
          <option v-for="emp in employees" :key="emp.id" :value="String(emp.id)">
            {{ emp.last_name }} {{ emp.first_name }}
          </option>
        </select>
      </div>

      <div class="filter-actions">
        <button
          v-if="!isEditMode"
          class="btn-primary"
          @click="toggleEditMode"
          :disabled="!selectedFloorId"
        >
          <i class="pi pi-pencil"></i> Редактировать камеры
        </button>

        <template v-else>
          <button class="btn-text" @click="cancelEditMode">
            Отмена
          </button>
          <button class="btn-success" @click="savePlan" :disabled="savingPlan || !selectedFloorId">
            <i class="pi pi-check"></i> {{ savingPlan ? 'Сохранение...' : 'Сохранить' }}
          </button>
        </template>
      </div>
    </div>

    <div class="tracking-grid">
      <div class="map-section">
        <div class="map-header">
          <div>
            <h2>{{ selectedBuildingName || 'Здание не выбрано' }}</h2>
            <p>{{ selectedFloorLabel || 'Выберите этаж для просмотра плана' }}</p>
          </div>
          <span class="plan-status" :class="currentFloor?.has_plan ? 'ready' : 'missing'">
            {{ currentFloor?.has_plan ? 'План загружен' : 'План не загружен' }}
          </span>
        </div>

        <div
          class="map-container"
          ref="mapContainer"
          @mousemove="onMapMouseMove"
          @mouseup="onMapMouseUp"
          @mouseleave="onMapMouseUp"
          :class="{ 'is-editing': isEditMode }"
        >
          <img
            v-if="selectedFloorId && currentFloor?.has_plan"
            :src="currentPlanUrl"
            alt="План этажа"
            class="building-plan"
            draggable="false"
            @error="onPlanImageError"
          />

          <div v-else class="plan-empty-state">
            <i class="pi pi-image"></i>
            <div class="plan-empty-title">Нет плана этажа</div>
            <div class="plan-empty-text">
              Выберите этаж и загрузите изображение плана, чтобы отображать камеры на карте.
            </div>
          </div>

          <div
            v-for="camera in mappedCameras"
            :key="camera.id"
            :class="['camera-pin', { 'active-pin': activeCameraId === camera.id }]"
            :style="cameraStyle(camera)"
            @mousedown.stop="startDrag(camera.id, $event)"
            @click.stop="onCameraClick(camera)"
            :title="camera.name"
          >
            <i class="pi pi-video"></i>
            <span class="pulse-ring" v-if="!isEditMode && activeCameraId === camera.id"></span>
            <div class="camera-tooltip">{{ camera.name }}</div>
          </div>
        </div>
      </div>

      <div class="logs-section" v-if="!isEditMode">
        <h2>Журнал проходов</h2>
        <div class="logs-list">
          <div v-for="log in filteredLogs" :key="log.id" class="log-card">
            <div class="log-time">{{ formatTime(log.timestamp) }}</div>
            <div class="log-info">
              <div class="log-name">{{ log.employee_name }}</div>
              <div class="log-camera">
                <i class="pi pi-map-marker"></i> {{ log.camera_name }}
              </div>
            </div>
          </div>
          <div v-if="filteredLogs.length === 0" class="empty-logs">
            Событий по выбранному этажу не найдено.
          </div>
        </div>
      </div>

      <div class="editor-sidebar" v-else>
        <h2>Настройка плана</h2>

        <div v-if="unassignedCameras.length > 0" class="unassigned-section">
          <h3>Свободные камеры</h3>
          <p class="instruction-small">Выберите камеру, чтобы разместить её на текущем этаже:</p>
          <div class="unassigned-list">
            <div v-for="cam in unassignedCameras" :key="cam.id" class="unassigned-card">
              <span class="cam-name-small">{{ cam.name }}</span>
              <button class="btn-secondary btn-sm" @click="addCameraToFloor(cam)" title="Добавить на план">
                <i class="pi pi-plus"></i>
              </button>
            </div>
          </div>
          <hr class="sidebar-divider" />
        </div>

        <div v-if="activeCamera" class="active-cam-info">
          <div class="info-group">
            <label>Выбрана камера</label>
            <div class="cam-name">{{ activeCamera.name }}</div>
          </div>
          <div class="info-group compact">
            <label>IP-адрес</label>
            <div class="cam-value">{{ activeCamera.ip_address }}</div>
          </div>
          <div class="info-group compact">
            <label>Позиция на плане</label>
            <div class="cam-value">
              X: {{ formatPercent(activeCamera.plan_x) }} · Y: {{ formatPercent(activeCamera.plan_y) }}
            </div>
          </div>

          <button class="btn-text btn-danger remove-btn" @click="removeCameraFromFloor(activeCamera.id)">
            <i class="pi pi-times"></i> Убрать с плана
          </button>
        </div>
        <div v-else class="empty-selection">
          <p class="instruction">
            Кликните по камере на плане, чтобы выбрать её, или перетащите иконку мышкой на нужное место.
          </p>
        </div>
      </div>
    </div>

    <div v-if="displayVideoDialog" class="modal-overlay" @click.self="closeVideoModal">
      <div class="modal-content video-modal">
        <div class="modal-header">
          <h2>Трансляция: {{ viewingCamera?.name }}</h2>
          <button class="btn-icon close-btn" @click="closeVideoModal">
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

    <div v-if="buildingModalVisible" class="modal-overlay" @click.self="closeBuildingModal">
      <div class="modal-content small-modal">
        <div class="modal-header">
          <h2>Новое здание</h2>
          <button class="btn-icon close-btn" @click="closeBuildingModal">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="form-group">
          <label>Название <span class="required">*</span></label>
          <input v-model="buildingForm.name" type="text" class="form-input" placeholder="Главный корпус" />
        </div>

        <div class="form-group">
          <label>Адрес</label>
          <input v-model="buildingForm.address" type="text" class="form-input" placeholder="ул. Пример, 1" />
        </div>

        <div class="modal-actions">
          <button class="btn-text" @click="closeBuildingModal">Отмена</button>
          <button class="btn-primary" @click="saveBuilding" :disabled="buildingSaving">
            {{ buildingSaving ? 'Сохранение...' : 'Сохранить' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="floorModalVisible" class="modal-overlay" @click.self="closeFloorModal">
      <div class="modal-content">
        <div class="modal-header">
          <h2>{{ floorForm.id ? 'Редактировать этаж' : 'Новый этаж' }}</h2>
          <button class="btn-icon close-btn" @click="closeFloorModal">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="form-grid">
          <div class="form-group">
            <label>Здание <span class="required">*</span></label>
            <select v-model="floorForm.building_id" class="form-input">
              <option value="" disabled>Выберите здание...</option>
              <option v-for="building in buildings" :key="building.id" :value="String(building.id)">
                {{ building.name }}
              </option>
            </select>
          </div>

          <div class="form-group">
            <label>Номер этажа <span class="required">*</span></label>
            <input v-model="floorForm.floor_number" type="number" class="form-input" placeholder="1" />
          </div>

          <div class="form-group full-width">
            <label>Название этажа <span class="required">*</span></label>
            <input v-model="floorForm.name" type="text" class="form-input" placeholder="Первый этаж" />
          </div>
        </div>

        <div class="form-group">
          <label>План этажа</label>
          <input type="file" accept="image/*" class="form-input" @change="onFloorPlanSelected" />
          <p class="upload-hint" v-if="floorForm.id && currentFloor?.has_plan">
            У текущего этажа уже есть план. Можно заменить его новым файлом.
          </p>
        </div>

        <div class="form-group checkbox-group" v-if="floorForm.id && currentFloor?.has_plan">
          <input id="removePlan" v-model="floorForm.remove_plan" type="checkbox" />
          <label for="removePlan">Удалить текущий план</label>
        </div>

        <div class="modal-actions">
          <button class="btn-text" @click="closeFloorModal">Отмена</button>
          <button class="btn-primary" @click="saveFloor" :disabled="floorSaving">
            {{ floorSaving ? 'Сохранение...' : 'Сохранить' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch, onBeforeUnmount } from 'vue'
import { analyticsApi } from '../api/analytics'
import { employeesApi } from '../api/employees'
import { camerasApi } from '../api/cameras'
import { buildingsApi } from '../api/buildings'
import { floorsApi } from '../api/floors'

const logs = ref([])
const employees = ref([])
const buildings = ref([])
const floors = ref([])
const mappedCameras = ref([])

const unassignedCameras = ref([])
const camerasToRemoveFromFloor = ref([])

const selectedBuildingId = ref('')
const selectedFloorId = ref('')
const selectedEmployeeId = ref('')
const activeCameraId = ref(null)

const isEditMode = ref(false)
const mapContainer = ref(null)
const draggingCameraId = ref(null)
const savingPlan = ref(false)
const floorsLoading = ref(false)
const planVersion = ref(Date.now())

const buildingModalVisible = ref(false)
const buildingSaving = ref(false)
const buildingForm = ref({ name: '', address: '' })

const floorModalVisible = ref(false)
const floorSaving = ref(false)
const floorForm = ref({ id: null, building_id: '', name: '', floor_number: '', planFile: null, remove_plan: false })

const displayVideoDialog = ref(false)
const viewingCamera = ref(null)
const currentFrame = ref(null)

let ws = null
let currentBlobUrl = null

const selectedBuilding = computed(() => buildings.value.find((item) => String(item.id) === String(selectedBuildingId.value)) || null)
const currentFloor = computed(() => floors.value.find((item) => String(item.id) === String(selectedFloorId.value)) || null)

const selectedBuildingName = computed(() => selectedBuilding.value?.name || '')
const selectedFloorLabel = computed(() => {
  if (!currentFloor.value) return ''
  return `${currentFloor.value.name} · ${currentFloor.value.floor_number} этаж`
})

const currentPlanUrl = computed(() => {
  if (!selectedFloorId.value || !currentFloor.value?.has_plan) return ''
  return `${floorsApi.getFloorPlanUrl(selectedFloorId.value)}?v=${planVersion.value}`
})

const activeCamera = computed(() => mappedCameras.value.find((camera) => camera.id === activeCameraId.value) || null)
const currentFloorCameraNames = computed(() => new Set(mappedCameras.value.map((camera) => camera.name)))

const filteredLogs = computed(() => {
  let result = logs.value
  if (currentFloorCameraNames.value.size > 0) {
    result = result.filter((log) => currentFloorCameraNames.value.has(log.camera_name))
  }
  if (selectedEmployeeId.value) {
    const employee = employees.value.find((item) => String(item.id) === String(selectedEmployeeId.value))
    if (employee) {
      const fullName = [employee.last_name, employee.first_name, employee.middle_name].filter(Boolean).join(' ')
      result = result.filter((log) => log.employee_name === fullName)
    }
  }
  return result
})

function cameraStyle(camera) {
  const x = typeof camera.plan_x === 'number' ? camera.plan_x : 0.5
  const y = typeof camera.plan_y === 'number' ? camera.plan_y : 0.5
  return { left: `${x * 100}%`, top: `${y * 100}%` }
}

function clamp01(value) {
  return Math.max(0, Math.min(1, value))
}

function formatPercent(value) {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—'
}

function formatTime(isoString) {
  return new Date(isoString).toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

function getMouseNormalized(event) {
  if (!mapContainer.value) return { x: 0.5, y: 0.5 }
  const rect = mapContainer.value.getBoundingClientRect()
  return {
    x: clamp01((event.clientX - rect.left) / rect.width),
    y: clamp01((event.clientY - rect.top) / rect.height)
  }
}

function selectCamera(id) {
  activeCameraId.value = id
}

function onCameraClick(camera) {
  if (isEditMode.value) {
    selectCamera(camera.id)
  } else {
    openVideoModal(camera)
  }
}

function getVideoWsUrl(cameraId) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = 'localhost:8000'
  return `${protocol}//${host}/ws/video/${cameraId}`
}

function cleanupFrameUrl() {
  if (currentBlobUrl) {
    URL.revokeObjectURL(currentBlobUrl)
    currentBlobUrl = null
  }
}

function openVideoModal(camera) {
  closeVideoModal()

  viewingCamera.value = camera
  displayVideoDialog.value = true
  currentFrame.value = null

  ws = new WebSocket(getVideoWsUrl(camera.id))
  ws.binaryType = 'blob'

  ws.onopen = () => {
    console.log('[video] websocket connected', camera.id)
  }

  ws.onmessage = (event) => {
    cleanupFrameUrl()

    const blob = event.data instanceof Blob
      ? event.data
      : new Blob([event.data], { type: 'image/jpeg' })

    currentBlobUrl = URL.createObjectURL(blob)
    currentFrame.value = currentBlobUrl
  }

  ws.onerror = (error) => {
    console.error('[video] websocket error', error)
    alert('Ошибка подключения к потоку камеры')
    closeVideoModal()
  }

  ws.onclose = (event) => {
    console.log('[video] websocket closed', event.code, event.reason)
  }
}

function closeVideoModal() {
  displayVideoDialog.value = false
  viewingCamera.value = null
  currentFrame.value = null

  cleanupFrameUrl()

  if (ws) {
    ws.onopen = null
    ws.onmessage = null
    ws.onerror = null
    ws.onclose = null
    ws.close()
    ws = null
  }
}

function startDrag(id, event) {
  if (!isEditMode.value) return
  selectCamera(id)
  if (event && typeof event.preventDefault === 'function') {
    event.preventDefault()
  }
  draggingCameraId.value = id
}

function onMapMouseMove(event) {
  if (!isEditMode.value || !draggingCameraId.value) return
  const camera = mappedCameras.value.find((item) => item.id === draggingCameraId.value)
  if (!camera) return

  const { x, y } = getMouseNormalized(event)
  camera.plan_x = x
  camera.plan_y = y
}

function onMapMouseUp() {
  draggingCameraId.value = null
}

async function loadUnassignedCameras() {
  try {
    const response = await camerasApi.getCameras()
    unassignedCameras.value = response.data.filter((c) => !c.floor_id)
  } catch (error) {
    console.error('Ошибка загрузки свободных камер:', error)
  }
}

function addCameraToFloor(camera) {
  mappedCameras.value.push({
    ...camera,
    plan_x: 0.5,
    plan_y: 0.5,
    building_id: Number(selectedBuildingId.value),
    floor_id: Number(selectedFloorId.value)
  })
  unassignedCameras.value = unassignedCameras.value.filter((c) => c.id !== camera.id)
  activeCameraId.value = camera.id
}

function removeCameraFromFloor(id) {
  const camIndex = mappedCameras.value.findIndex((c) => c.id === id)
  if (camIndex > -1) {
    const cam = mappedCameras.value[camIndex]
    mappedCameras.value.splice(camIndex, 1)
    unassignedCameras.value.push(cam)
    camerasToRemoveFromFloor.value.push(cam.id)
    if (activeCameraId.value === id) {
      activeCameraId.value = null
    }
  }
}

async function toggleEditMode() {
  if (!selectedFloorId.value) return
  isEditMode.value = true
  activeCameraId.value = null
  camerasToRemoveFromFloor.value = []
  await loadUnassignedCameras()
}

function cancelEditMode() {
  isEditMode.value = false
  activeCameraId.value = null
  draggingCameraId.value = null
  camerasToRemoveFromFloor.value = []
  loadFloorContext()
}

async function savePlan() {
  if (!selectedFloorId.value) return
  savingPlan.value = true
  try {
    const updatePromises = mappedCameras.value.map((camera) =>
      camerasApi.updateCamera(camera.id, {
        building_id: currentFloor.value?.building_id ?? null,
        floor_id: currentFloor.value?.id ?? null,
        plan_x: clamp01(typeof camera.plan_x === 'number' ? camera.plan_x : 0.5),
        plan_y: clamp01(typeof camera.plan_y === 'number' ? camera.plan_y : 0.5)
      })
    )

    const removePromises = camerasToRemoveFromFloor.value.map((camId) =>
      camerasApi.updateCamera(camId, {
        building_id: null,
        floor_id: null,
        plan_x: null,
        plan_y: null
      })
    )

    await Promise.all([...updatePromises, ...removePromises])

    isEditMode.value = false
    activeCameraId.value = null
    camerasToRemoveFromFloor.value = []
    await loadFloorContext()
    alert('Положение камер успешно сохранено.')
  } catch (error) {
    alert(error.response?.data?.detail || 'Не удалось сохранить позиции камер')
  } finally {
    savingPlan.value = false
  }
}

function onPlanImageError(event) {
  event.target.style.display = 'none'
}

async function loadInitialData() {
  try {
    const [logsRes, empRes, buildingsRes] = await Promise.all([
      analyticsApi.getAccessLogs(100),
      employeesApi.getEmployees(),
      buildingsApi.getBuildings()
    ])
    logs.value = logsRes.data
    employees.value = empRes.data
    buildings.value = buildingsRes.data

    if (!selectedBuildingId.value && buildings.value.length > 0) {
      selectedBuildingId.value = String(buildings.value[0].id)
    } else if (selectedBuildingId.value) {
      await loadFloorsForBuilding(selectedBuildingId.value)
    }
  } catch (error) {
    alert('Не удалось загрузить данные страницы плана здания')
  }
}

async function loadFloorsForBuilding(buildingId) {
  floorsLoading.value = true
  try {
    const response = await floorsApi.getFloors(buildingId)
    floors.value = response.data
    const currentStillExists = floors.value.some((item) => String(item.id) === String(selectedFloorId.value))
    if (!currentStillExists) {
      selectedFloorId.value = floors.value.length > 0 ? String(floors.value[0].id) : ''
    }
  } catch (error) {
    floors.value = []
    selectedFloorId.value = ''
    alert(error.response?.data?.detail || 'Не удалось загрузить этажи')
  } finally {
    floorsLoading.value = false
  }
}

async function loadFloorContext() {
  if (!selectedBuildingId.value || !selectedFloorId.value) {
    mappedCameras.value = []
    activeCameraId.value = null
    return
  }
  try {
    const [floorRes, camerasRes] = await Promise.all([
      floorsApi.getFloor(selectedFloorId.value),
      camerasApi.getCameras({ buildingId: selectedBuildingId.value, floorId: selectedFloorId.value })
    ])
    const floor = floorRes.data
    floors.value = floors.value.map((item) => (item.id === floor.id ? floor : item))
    mappedCameras.value = camerasRes.data.map((camera, index) => ({
      ...camera,
      plan_x: typeof camera.plan_x === 'number' && camera.plan_x !== null ? camera.plan_x : distributeFallbackX(index, camerasRes.data.length),
      plan_y: typeof camera.plan_y === 'number' && camera.plan_y !== null ? camera.plan_y : 0.5
    }))
    if (!mappedCameras.value.some((item) => item.id === activeCameraId.value)) {
      activeCameraId.value = null
    }
    planVersion.value = Date.now()
  } catch (error) {
    mappedCameras.value = []
    activeCameraId.value = null
    alert(error.response?.data?.detail || 'Не удалось загрузить данные этажа')
  }
}

function distributeFallbackX(index, total) {
  if (total <= 1) return 0.5
  return 0.15 + (0.7 / (total - 1)) * index
}

function openBuildingModal() {
  buildingForm.value = { name: '', address: '' }
  buildingModalVisible.value = true
}

function closeBuildingModal() {
  buildingModalVisible.value = false
  buildingSaving.value = false
}

async function saveBuilding() {
  if (!buildingForm.value.name.trim()) return alert('Введите название здания')
  buildingSaving.value = true
  try {
    const response = await buildingsApi.createBuilding({
      name: buildingForm.value.name.trim(),
      address: buildingForm.value.address.trim() || null
    })
    await loadInitialData()
    selectedBuildingId.value = String(response.data.id)
    closeBuildingModal()
  } catch (error) {
    alert(error.response?.data?.detail || 'Не удалось создать здание')
  } finally {
    buildingSaving.value = false
  }
}

function openFloorModal(editCurrent = false) {
  if (!selectedBuildingId.value) return alert('Сначала выберите или создайте здание')
  if (editCurrent && currentFloor.value) {
    floorForm.value = {
      id: currentFloor.value.id,
      building_id: String(currentFloor.value.building_id),
      name: currentFloor.value.name,
      floor_number: String(currentFloor.value.floor_number),
      planFile: null,
      remove_plan: false
    }
  } else {
    floorForm.value = {
      id: null,
      building_id: String(selectedBuildingId.value),
      name: '',
      floor_number: '',
      planFile: null,
      remove_plan: false
    }
  }
  floorModalVisible.value = true
}

function closeFloorModal() {
  floorModalVisible.value = false
  floorSaving.value = false
  floorForm.value = { id: null, building_id: '', name: '', floor_number: '', planFile: null, remove_plan: false }
}

function onFloorPlanSelected(event) {
  floorForm.value.planFile = event.target.files?.[0] || null
}

async function saveFloor() {
  if (!floorForm.value.building_id || !floorForm.value.name.trim() || floorForm.value.floor_number === '') {
    return alert('Заполните обязательные поля этажа')
  }

  const formData = new FormData()
  formData.append('building_id', String(floorForm.value.building_id))
  formData.append('name', floorForm.value.name.trim())
  formData.append('floor_number', String(floorForm.value.floor_number))
  if (floorForm.value.planFile) formData.append('plan', floorForm.value.planFile)
  if (floorForm.value.id && floorForm.value.remove_plan) formData.append('remove_plan', 'true')

  floorSaving.value = true
  try {
    let response
    if (floorForm.value.id) {
      response = await floorsApi.updateFloor(floorForm.value.id, formData)
    } else {
      response = await floorsApi.createFloor(formData)
    }
    const targetBuildingId = String(floorForm.value.building_id)
    await loadInitialData()
    selectedBuildingId.value = targetBuildingId
    await loadFloorsForBuilding(targetBuildingId)
    selectedFloorId.value = String(response.data.id)
    closeFloorModal()
  } catch (error) {
    alert(error.response?.data?.detail || 'Не удалось сохранить этаж')
  } finally {
    floorSaving.value = false
  }
}

let trackingIntervalId = null

function simulateRealtimeTracking() {
  if (trackingIntervalId) clearInterval(trackingIntervalId)
  trackingIntervalId = window.setInterval(() => {
    if (isEditMode.value || filteredLogs.value.length === 0) return
    const latestLog = filteredLogs.value[0]
    const targetCam = mappedCameras.value.find((camera) => camera.name === latestLog.camera_name)
    if (!targetCam) return
    activeCameraId.value = targetCam.id
    window.setTimeout(() => {
      if (!isEditMode.value) activeCameraId.value = null
    }, 2000)
  }, 5000)
}

watch(selectedBuildingId, async (newValue) => {
  isEditMode.value = false
  activeCameraId.value = null
  mappedCameras.value = []
  floors.value = []
  selectedFloorId.value = ''
  if (!newValue) return
  await loadFloorsForBuilding(newValue)
})

watch(selectedFloorId, async (newValue) => {
  isEditMode.value = false
  activeCameraId.value = null
  if (!newValue) {
    mappedCameras.value = []
    return
  }
  await loadFloorContext()
})

onMounted(async () => {
  await loadInitialData()
  // simulateRealtimeTracking()
})

onBeforeUnmount(() => {
  closeVideoModal()
  if (trackingIntervalId) clearInterval(trackingIntervalId)
})
</script>

<style scoped>
.page-container { height: 100%; display: flex; flex-direction: column; gap: 1rem; }
.header-panel, .filters-row, .map-section, .logs-section, .editor-sidebar { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04); }
.header-panel { display: flex; justify-content: space-between; align-items: flex-start; padding: 1.25rem 1.5rem; }
.page-title { font-size: 1.5rem; font-weight: 600; color: #0f172a; margin: 0; }
.page-subtitle { margin: 0.35rem 0 0; color: #64748b; font-size: 0.9rem; }
.top-buttons, .filter-actions { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
.filters-row { display: grid; grid-template-columns: minmax(220px, 1fr) minmax(220px, 1fr) minmax(220px, 1fr) auto; gap: 1rem; padding: 1rem 1.25rem; align-items: end; }
.filter-group { display: flex; flex-direction: column; gap: 0.4rem; }
.filter-group label { font-size: 0.85rem; color: #475569; font-weight: 600; }
.form-input { width: 100%; padding: 0.7rem 0.9rem; border-radius: 8px; border: 1px solid #cbd5e1; background: #f8fafc; font-size: 0.95rem; color: #1e293b; }
.form-input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12); background: #ffffff; }

.btn-primary, .btn-secondary, .btn-success, .btn-text { border: none; border-radius: 8px; padding: 0.65rem 1rem; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 0.5rem; }
.btn-primary { background: #3b82f6; color: #ffffff; }
.btn-secondary { background: #eef2ff; color: #334155; }
.btn-success { background: #10b981; color: #ffffff; }
.btn-text { background: transparent; color: #64748b; }
.btn-primary:disabled, .btn-secondary:disabled, .btn-success:disabled, .btn-text:disabled { opacity: 0.6; cursor: not-allowed; }

.tracking-grid { display: grid; grid-template-columns: 2.1fr 1fr; gap: 1rem; flex: 1; min-height: 0; }
.map-section, .logs-section, .editor-sidebar { display: flex; flex-direction: column; padding: 1rem; min-height: 0; }
.map-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; gap: 1rem; }
.map-header h2, .logs-section h2, .editor-sidebar h2 { margin: 0; font-size: 1.15rem; color: #0f172a; }
.map-header p { margin: 0.25rem 0 0; color: #64748b; font-size: 0.88rem; }

.plan-status { padding: 0.35rem 0.7rem; border-radius: 999px; font-size: 0.75rem; font-weight: 700; }
.plan-status.ready { background: #dcfce7; color: #166534; }
.plan-status.missing { background: #fef3c7; color: #92400e; }

.map-container { position: relative; flex: 1; min-height: 520px; background: #f8fafc; border-radius: 10px; overflow: hidden; border: 1px solid #e2e8f0; }
.map-container.is-editing { cursor: move; }
.building-plan { width: 100%; height: 100%; object-fit: contain; pointer-events: none; }
.plan-empty-state { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.75rem; color: #94a3b8; text-align: center; padding: 2rem; }
.plan-empty-state i { font-size: 2rem; }
.plan-empty-title { color: #475569; font-weight: 700; }
.plan-empty-text { max-width: 360px; line-height: 1.4; }

.camera-pin { position: absolute; width: 30px; height: 30px; border-radius: 50%; background: #3b82f6; color: #ffffff; display: flex; align-items: center; justify-content: center; transform: translate(-50%, -50%); box-shadow: 0 4px 10px rgba(15, 23, 42, 0.2); cursor: pointer; z-index: 2; }
.is-editing .camera-pin { cursor: grab; }
.is-editing .camera-pin:active { cursor: grabbing; }
.camera-pin.active-pin { background: #10b981; box-shadow: 0 0 0 5px rgba(16, 185, 129, 0.18); }
.camera-tooltip { display: none; position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%); background: #0f172a; color: white; padding: 0.35rem 0.55rem; border-radius: 6px; font-size: 0.75rem; white-space: nowrap; }
.camera-pin:hover .camera-tooltip { display: block; }

.pulse-ring { position: absolute; inset: -2px; border: 2px solid #10b981; border-radius: 50%; animation: pulse 1.5s infinite; }
@keyframes pulse { 0% { transform: scale(1); opacity: 1; } 100% { transform: scale(2.4); opacity: 0; } }

.logs-list { margin-top: 1rem; overflow-y: auto; display: flex; flex-direction: column; gap: 0.75rem; }
.log-card { display: flex; gap: 1rem; align-items: center; padding: 0.8rem 0.9rem; border-radius: 8px; background: #f8fafc; border: 1px solid #e2e8f0; }
.log-time { font-family: monospace; font-size: 0.82rem; color: #64748b; min-width: 70px; }
.log-name { color: #0f172a; font-weight: 600; }
.log-camera { margin-top: 0.2rem; font-size: 0.82rem; color: #64748b; display: flex; align-items: center; gap: 0.3rem; }
.empty-logs, .empty-selection { margin: auto 0; text-align: center; color: #94a3b8; }

.unassigned-section { margin-bottom: 1.5rem; }
.unassigned-section h3 { font-size: 1.05rem; margin: 0 0 0.5rem 0; color: #0f172a; }
.instruction-small { font-size: 0.82rem; color: #64748b; margin: 0 0 0.75rem 0; line-height: 1.3; }
.unassigned-list { display: flex; flex-direction: column; gap: 0.5rem; max-height: 220px; overflow-y: auto; padding-right: 0.25rem; }
.unassigned-card { display: flex; justify-content: space-between; align-items: center; background: #f1f5f9; padding: 0.55rem 0.8rem; border-radius: 8px; border: 1px solid #e2e8f0; }
.cam-name-small { font-size: 0.88rem; font-weight: 600; color: #334155; }
.btn-sm { padding: 0.35rem 0.6rem; font-size: 0.85rem; }
.btn-danger { color: #ef4444; }
.btn-danger:hover { color: #dc2626; background: #fee2e2; }
.remove-btn { margin-top: 1rem; width: 100%; justify-content: center; border: 1px solid #fecaca; }
.sidebar-divider { border: 0; height: 1px; background: #e2e8f0; margin: 1.5rem 0; }

.active-cam-info { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1rem; }
.info-group { margin-bottom: 1rem; }
.info-group.compact { margin-bottom: 0.8rem; }
.info-group label { display: block; color: #64748b; font-size: 0.82rem; margin-bottom: 0.25rem; }
.cam-name, .cam-value { color: #0f172a; font-weight: 600; }
.instruction { color: #475569; line-height: 1.5; margin: 0; font-size: 0.9rem; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { width: min(1100px, calc(100vw - 2rem)); background: #ffffff; border-radius: 16px; padding: 1.5rem; box-shadow: 0 20px 40px rgba(15, 23, 42, 0.25); }
.small-modal { width: min(460px, calc(100vw - 2rem)); }

.video-modal { max-width: 1200px; padding: 1.5rem; }
.video-container { width: 100%; aspect-ratio: 4 / 3; background-color: #0f172a; border-radius: 6px; overflow: hidden; display: flex; align-items: center; justify-content: center; }
.live-video { width: 100%; height: 100%; object-fit: contain; }
.video-placeholder { color: #cbd5e1; display: flex; flex-direction: column; align-items: center; gap: 1rem; }

.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; }
.modal-header h2 { margin: 0; font-size: 1.2rem; color: #0f172a; }
.btn-icon { border: none; background: transparent; cursor: pointer; color: #64748b; font-size: 1rem; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.full-width { grid-column: 1 / -1; }
.form-group { display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 1rem; }
.form-group label { color: #475569; font-weight: 600; font-size: 0.85rem; }
.required { color: #ef4444; }
.checkbox-group { flex-direction: row; align-items: center; }
.upload-hint { margin: 0; color: #64748b; font-size: 0.8rem; }
.modal-actions { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 0.75rem; }

@media (max-width: 1200px) {
  .filters-row { grid-template-columns: 1fr 1fr; }
  .tracking-grid { grid-template-columns: 1fr; }
  .map-container { min-height: 420px; }
}
@media (max-width: 768px) {
  .header-panel { flex-direction: column; gap: 1rem; }
  .filters-row, .form-grid { grid-template-columns: 1fr; }
}
</style>