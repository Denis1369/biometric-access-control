<template>
  <div class="page-container">
    <div class="header-panel">
      <div>
        <h1 class="page-title">План здания</h1>
        <p class="page-subtitle">Выбор здания, этажа, загрузка плана, расстановка камер и маршрут гостей.</p>
      </div>

      <div class="top-buttons">
        <button v-if="canEditPlan" class="btn-secondary" @click="openBuildingModal()">
          <i class="pi pi-building"></i> Новое здание
        </button>
        <button v-if="canEditPlan" class="btn-secondary" @click="openFloorModal()" :disabled="!selectedBuildingId">
          <i class="pi pi-plus"></i> Новый этаж
        </button>
        <button v-if="canEditPlan" class="btn-secondary" @click="openFloorModal(true)" :disabled="!selectedFloorId">
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
        <label>Гость</label>
        <select v-model="selectedGuestId" class="form-input">
          <option value="">Все гости</option>
          <option v-for="guest in guests" :key="guest.id" :value="String(guest.id)">
            {{ buildGuestName(guest) }}
          </option>
        </select>
      </div>

      <div class="filter-group compact" v-if="!isEditMode">
        <label>Дата маршрута</label>
        <input v-model="routeDate" type="date" class="form-input" />
      </div>

      <div class="filter-actions">
        <button
          v-if="canEditPlan && !isEditMode"
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

          <svg
            v-if="mapOverlayVisible"
            class="map-overlay-layer"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <template v-if="showPlanAnalysis && planAnalysis">
              <polygon
                v-for="(room, index) in analysisRoomsOnMap"
                :key="`room-${index}`"
                :points="room.points"
                class="analysis-room"
              />
              <polygon
                v-for="(corridor, index) in analysisCorridorsOnMap"
                :key="`corridor-${index}`"
                :points="corridor.points"
                class="analysis-corridor"
              />
              <line
                v-for="(wall, index) in analysisWallsOnMap"
                :key="`wall-${index}`"
                :x1="wall.x1"
                :y1="wall.y1"
                :x2="wall.x2"
                :y2="wall.y2"
                class="analysis-wall"
              />
              <line
                v-for="(door, index) in analysisDoorsOnMap"
                :key="`door-${index}`"
                :x1="door.x1"
                :y1="door.y1"
                :x2="door.x2"
                :y2="door.y2"
                class="analysis-door"
              />
            </template>
            <polygon
              v-for="zone in visibilityZonesOnMap"
              :key="zone.key"
              :points="zone.points"
              :class="['camera-zone', { active: zone.active, editable: isEditMode }]"
              @mousedown.stop="startZoneDrag(zone.cameraId, $event)"
            />
            <path
              v-for="routePath in routePathsOnMap"
              :key="routePath.key"
              :d="routePath.d"
              class="route-curve-line"
            />
          </svg>

          <template v-if="isEditMode && activeCamera?.visibility_polygon">
            <div
              v-for="(point, index) in activeCamera.visibility_polygon"
              :key="`zone-handle-${activeCamera.id}-${index}`"
              class="zone-handle"
              :style="zoneHandleStyle(point)"
              @mousedown.stop="startZoneHandleDrag(activeCamera.id, index, $event)"
              :title="`Угол зоны видимости #${index + 1}`"
            >
              {{ index + 1 }}
            </div>
          </template>

          <svg
            v-if="!isEditMode && topologyEdgesOnMap.length > 0"
            class="topology-layer"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <defs>
              <marker
                id="topology-arrow"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="4"
                markerHeight="4"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" />
              </marker>
            </defs>
            <line
              v-for="edge in topologyEdgesOnMap"
              :key="edge.key"
              :x1="edge.x1"
              :y1="edge.y1"
              :x2="edge.x2"
              :y2="edge.y2"
              :class="['topology-edge', edge.className]"
              marker-end="url(#topology-arrow)"
            />
          </svg>

          <div
            v-for="camera in mappedCameras"
            :key="camera.id"
            :class="['camera-pin', { 'active-pin': activeCameraId === camera.id, 'route-pin': routeStepByCameraId.has(camera.id) }]"
            :style="cameraStyle(camera)"
            @mousedown.stop="startDrag(camera.id, $event)"
            @click.stop="onCameraClick(camera)"
            :title="camera.name"
          >
            <i class="pi pi-video"></i>
            <span v-if="routeStepByCameraId.get(camera.id)" class="route-step">
              {{ routeStepByCameraId.get(camera.id) }}
            </span>
            <span class="pulse-ring" v-if="!isEditMode && activeCameraId === camera.id"></span>
            <div class="camera-tooltip">{{ camera.name }}</div>
          </div>
        </div>
      </div>

      <div class="logs-section" v-if="!isEditMode">
        <div class="route-header">
          <div>
            <h2>Маршрут гостя</h2>
            <p>{{ selectedGuestName || 'Все гости' }}</p>
          </div>
          <span class="route-count">{{ currentFloorRoutePoints.length }}</span>
        </div>
        <div class="logs-list">
          <div v-for="point in currentFloorRoutePoints" :key="point.id" class="log-card route-card">
            <div class="log-time">{{ formatTime(point.timestamp) }}</div>
            <div class="log-info">
              <div class="log-name">{{ point.guest_name }}</div>
              <div class="log-camera">
                <i class="pi pi-map-marker"></i> {{ point.camera_name || 'Камера не указана' }}
              </div>
              <div class="route-meta">
                {{ point.floor_name || 'Этаж не указан' }}
                <span v-if="point.confidence !== null">· {{ formatConfidence(point.confidence) }}</span>
              </div>
            </div>
          </div>
          <div v-if="currentFloorRoutePoints.length === 0" class="empty-logs">
            Маршрутных событий по выбранному этажу не найдено.
          </div>
        </div>

        <div class="topology-section">
          <div class="route-header topology-header">
            <div>
              <h2>Связи камер</h2>
              <p>Автоопределение порядка за {{ TOPOLOGY_DAYS }} дней</p>
            </div>
            <span class="route-count topology-count">{{ currentFloorTransitions.length }}</span>
          </div>

          <div class="topology-list">
            <div
              v-for="edge in currentFloorTransitions"
              :key="`${edge.from_camera_id}-${edge.to_camera_id}`"
              class="transition-card"
            >
              <div class="transition-main">
                <span>{{ edge.from_camera_name }}</span>
                <i class="pi pi-arrow-right"></i>
                <span>{{ edge.to_camera_name }}</span>
              </div>
              <div class="transition-meta">
                {{ edge.transition_count }} переходов
                · {{ edge.unique_person_count }} чел.
                · медиана {{ formatDuration(edge.median_travel_seconds) }}
                · {{ formatConfidence(edge.confidence) }}
              </div>
            </div>
            <div v-if="currentFloorTransitions.length === 0" class="empty-topology">
              Пока мало событий для определения порядка камер.
            </div>
          </div>
        </div>
      </div>

      <div class="editor-sidebar" v-else>
        <h2>Настройка плана</h2>

        <div class="plan-analysis-section">
          <h3>Анализ плана</h3>
          <p class="instruction-small">
            Авторазбор плана подсвечивает стены, помещения, коридоры и возможные двери. Это подсказка, а не замена ручной разметки зон камер.
          </p>
          <div class="zone-actions">
            <button
              class="btn-secondary btn-sm"
              @click="loadPlanAnalysis"
              :disabled="planAnalysisLoading || !currentFloor?.has_plan"
            >
              <i class="pi pi-search"></i> {{ planAnalysisLoading ? 'Анализ...' : 'Найти элементы' }}
            </button>
            <button class="btn-text btn-sm" @click="showPlanAnalysis = !showPlanAnalysis" :disabled="!planAnalysis">
              {{ showPlanAnalysis ? 'Скрыть' : 'Показать' }}
            </button>
          </div>
          <div v-if="planAnalysis" class="analysis-stats">
            {{ planAnalysis.walls?.length || 0 }} стен ·
            {{ planAnalysis.corridors?.length || 0 }} коридоров ·
            {{ planAnalysis.rooms?.length || 0 }} комнат ·
            {{ planAnalysis.doors?.length || 0 }} дверей
          </div>
          <hr class="sidebar-divider" />
        </div>

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

          <div class="info-group compact">
            <label>Зона видимости</label>
            <div class="cam-value">
              {{ hasVisibilityPolygon(activeCamera) ? '4 точки размечены' : 'Не размечена' }}
            </div>
          </div>

          <div class="zone-editor-actions">
            <button class="btn-secondary btn-sm" @click="resetActiveCameraZone">
              <i class="pi pi-vector-square"></i> {{ hasVisibilityPolygon(activeCamera) ? 'Сбросить зону' : 'Создать зону' }}
            </button>
            <button class="btn-text btn-sm btn-danger" @click="clearActiveCameraZone" :disabled="!hasVisibilityPolygon(activeCamera)">
              Очистить
            </button>
          </div>
          <p class="instruction-small">
            Перетаскивайте углы 4-угольника на плане, чтобы примерно отметить участок, который видит камера.
          </p>

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
          <canvas
            ref="videoCanvas"
            v-show="hasVideoFrame"
            class="live-video live-video-canvas"
          ></canvas>
          <div v-if="!hasVideoFrame" class="video-placeholder">
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
import { computed, onMounted, ref, watch, onBeforeUnmount, nextTick } from 'vue'
import { analyticsApi } from '../api/analytics'
import { camerasApi } from '../api/cameras'
import { buildingsApi } from '../api/buildings'
import { floorsApi } from '../api/floors'
import { guestsApi } from '../api/guests'
import { buildWsUrl } from '../api/client'
import { useAuth } from '../services/auth'
import { createCanvasStreamPlayer } from '../services/liveStream'
import { useUi } from '../services/ui'

defineOptions({ name: 'TrackingPage' })

const auth = useAuth()
const ui = useUi()
const canEditPlan = computed(() => auth.hasAnyRole('super_admin'))
const TOPOLOGY_DAYS = 30

const routePoints = ref([])
const cameraTransitions = ref([])
const planAnalysis = ref(null)
const showPlanAnalysis = ref(true)
const planAnalysisLoading = ref(false)
const guests = ref([])
const buildings = ref([])
const floors = ref([])
const mappedCameras = ref([])

const unassignedCameras = ref([])
const camerasToRemoveFromFloor = ref([])

const selectedBuildingId = ref('')
const selectedFloorId = ref('')
const selectedGuestId = ref('')
const activeCameraId = ref(null)

const isEditMode = ref(false)
const mapContainer = ref(null)
const draggingCameraId = ref(null)
const draggingZone = ref(null)
const draggingZoneHandle = ref(null)
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
const hasVideoFrame = ref(false)
const videoCanvas = ref(null)

let livePlayer = null

const toLocalDateInputValue = (value = new Date()) => {
  const offsetMs = value.getTimezoneOffset() * 60000
  return new Date(value.getTime() - offsetMs).toISOString().slice(0, 10)
}

const routeDate = ref(toLocalDateInputValue())

const selectedBuilding = computed(() => buildings.value.find((item) => String(item.id) === String(selectedBuildingId.value)) || null)
const currentFloor = computed(() => floors.value.find((item) => String(item.id) === String(selectedFloorId.value)) || null)

const selectedBuildingName = computed(() => selectedBuilding.value?.name || '')
const selectedFloorLabel = computed(() => {
  if (!currentFloor.value) return ''
  return `${currentFloor.value.name} · ${currentFloor.value.floor_number} этаж`
})

const currentPlanUrl = computed(() => {
  if (!selectedFloorId.value || !currentFloor.value?.has_plan) return ''
  const baseUrl = floorsApi.getFloorPlanUrl(selectedFloorId.value)
  const separator = baseUrl.includes('?') ? '&' : '?'
  
  return `${baseUrl}${separator}v=${planVersion.value}`
})

const activeCamera = computed(() => mappedCameras.value.find((camera) => camera.id === activeCameraId.value) || null)
const selectedGuestName = computed(() => {
  const guest = guests.value.find((item) => String(item.id) === String(selectedGuestId.value))
  return guest ? buildGuestName(guest) : ''
})

const currentFloorRoutePoints = computed(() => {
  if (!selectedFloorId.value) return routePoints.value
  return routePoints.value.filter((point) => String(point.floor_id) === String(selectedFloorId.value))
})

const cameraById = computed(() => new Map(mappedCameras.value.map((camera) => [camera.id, camera])))

const currentFloorTransitions = computed(() => cameraTransitions.value.filter((edge) => {
  const fromCamera = cameraById.value.get(edge.from_camera_id)
  const toCamera = cameraById.value.get(edge.to_camera_id)
  return Boolean(fromCamera && toCamera)
}))

const visibilityZonesOnMap = computed(() => {
  return mappedCameras.value
    .map((camera) => {
      const polygon = normalizeVisibilityPolygon(camera.visibility_polygon)
      if (!polygon) return null
      return {
        key: `zone-${camera.id}`,
        cameraId: camera.id,
        active: activeCameraId.value === camera.id,
        points: polygon.map((point) => `${point.x * 100},${point.y * 100}`).join(' '),
      }
    })
    .filter(Boolean)
})

const topologyEdgesOnMap = computed(() => {
  return currentFloorTransitions.value
    .map((edge) => {
      const fromCamera = cameraById.value.get(edge.from_camera_id)
      const toCamera = cameraById.value.get(edge.to_camera_id)
      if (!fromCamera || !toCamera) return null

      const fromX = Number(fromCamera.plan_x ?? 0.5) * 100
      const fromY = Number(fromCamera.plan_y ?? 0.5) * 100
      const toX = Number(toCamera.plan_x ?? 0.5) * 100
      const toY = Number(toCamera.plan_y ?? 0.5) * 100
      const dx = toX - fromX
      const dy = toY - fromY
      const length = Math.hypot(dx, dy)
      if (length < 0.1) return null

      const offset = 3
      const unitX = dx / length
      const unitY = dy / length

      return {
        key: `${edge.from_camera_id}-${edge.to_camera_id}`,
        x1: fromX + unitX * offset,
        y1: fromY + unitY * offset,
        x2: toX - unitX * offset,
        y2: toY - unitY * offset,
        className: topologyConfidenceClass(edge.confidence),
      }
    })
    .filter(Boolean)
})

const routePathsOnMap = computed(() => {
  const paths = []
  let currentPoints = []
  let currentGuestId = null

  const flush = () => {
    if (currentPoints.length >= 2) {
      paths.push({
        key: `route-${paths.length + 1}-${currentGuestId ?? 'guest'}`,
        d: buildSmoothRoutePath(currentPoints),
      })
    }
    currentPoints = []
    currentGuestId = null
  }

  currentFloorRoutePoints.value.forEach((point) => {
    const x = Number(point.plan_x)
    const y = Number(point.plan_y)
    if (Number.isNaN(x) || Number.isNaN(y)) {
      flush()
      return
    }
    if (currentGuestId !== null && currentGuestId !== point.guest_id) {
      flush()
    }
    currentGuestId = point.guest_id
    currentPoints.push({ x: x * 100, y: y * 100 })
  })
  flush()

  return paths.filter((path) => path.d)
})

const analysisWallsOnMap = computed(() => normalizeAnalysisLines(planAnalysis.value?.walls))
const analysisDoorsOnMap = computed(() => normalizeAnalysisLines(planAnalysis.value?.doors))
const analysisRoomsOnMap = computed(() => normalizeAnalysisPolygons(planAnalysis.value?.rooms))
const analysisCorridorsOnMap = computed(() => normalizeAnalysisPolygons(planAnalysis.value?.corridors))

const mapOverlayVisible = computed(() => {
  return (
    visibilityZonesOnMap.value.length > 0 ||
    routePathsOnMap.value.length > 0 ||
    (showPlanAnalysis.value && planAnalysis.value)
  )
})

const routeStepByCameraId = computed(() => {
  const steps = new Map()
  currentFloorRoutePoints.value.forEach((point, index) => {
    if (point.camera_id && !steps.has(point.camera_id)) {
      steps.set(point.camera_id, index + 1)
    }
  })
  return steps
})

function cameraStyle(camera) {
  const x = typeof camera.plan_x === 'number' ? camera.plan_x : 0.5
  const y = typeof camera.plan_y === 'number' ? camera.plan_y : 0.5
  return { left: `${x * 100}%`, top: `${y * 100}%` }
}

function clamp01(value) {
  return Math.max(0, Math.min(1, value))
}

function normalizeVisibilityPolygon(value) {
  if (!Array.isArray(value) || value.length !== 4) return null
  const points = value
    .map((point) => ({
      x: clamp01(Number(point?.x)),
      y: clamp01(Number(point?.y)),
    }))
    .filter((point) => !Number.isNaN(point.x) && !Number.isNaN(point.y))
  return points.length === 4 ? points : null
}

function hasVisibilityPolygon(camera) {
  return Boolean(camera && normalizeVisibilityPolygon(camera.visibility_polygon))
}

function zoneHandleStyle(point) {
  return {
    left: `${clamp01(Number(point?.x)) * 100}%`,
    top: `${clamp01(Number(point?.y)) * 100}%`,
  }
}

function buildDefaultVisibilityPolygon(camera) {
  const x = clamp01(Number(camera?.plan_x ?? 0.5))
  const y = clamp01(Number(camera?.plan_y ?? 0.5))
  const nearHalfWidth = 0.045
  const farHalfWidth = 0.13
  const nearOffset = 0.035
  const farOffset = 0.22
  return [
    { x: clamp01(x - nearHalfWidth), y: clamp01(y - nearOffset) },
    { x: clamp01(x + nearHalfWidth), y: clamp01(y - nearOffset) },
    { x: clamp01(x + farHalfWidth), y: clamp01(y + farOffset) },
    { x: clamp01(x - farHalfWidth), y: clamp01(y + farOffset) },
  ]
}

function normalizeAnalysisLines(value) {
  return (Array.isArray(value) ? value : [])
    .map((line) => ({
      x1: clamp01(Number(line?.x1)) * 100,
      y1: clamp01(Number(line?.y1)) * 100,
      x2: clamp01(Number(line?.x2)) * 100,
      y2: clamp01(Number(line?.y2)) * 100,
    }))
    .filter((line) => Object.values(line).every((item) => !Number.isNaN(item)))
}

function normalizeAnalysisPolygons(value) {
  return (Array.isArray(value) ? value : [])
    .map((item) => {
      const polygon = Array.isArray(item?.polygon) ? item.polygon : []
      const points = polygon
        .map((point) => {
          const x = clamp01(Number(point?.x))
          const y = clamp01(Number(point?.y))
          if (Number.isNaN(x) || Number.isNaN(y)) return null
          return `${x * 100},${y * 100}`
        })
        .filter(Boolean)
      return points.length >= 3 ? { points: points.join(' ') } : null
    })
    .filter(Boolean)
}

function buildSmoothRoutePath(points) {
  if (!Array.isArray(points) || points.length < 2) return ''
  const commands = [`M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`]

  for (let index = 1; index < points.length - 1; index += 1) {
    const previous = points[index - 1]
    const current = points[index]
    const next = points[index + 1]
    const incoming = Math.hypot(current.x - previous.x, current.y - previous.y)
    const outgoing = Math.hypot(next.x - current.x, next.y - current.y)
    const radius = Math.min(4.5, incoming * 0.35, outgoing * 0.35)

    if (radius < 0.5 || incoming < 0.1 || outgoing < 0.1) {
      commands.push(`L ${current.x.toFixed(2)} ${current.y.toFixed(2)}`)
      continue
    }

    const inX = (current.x - previous.x) / incoming
    const inY = (current.y - previous.y) / incoming
    const outX = (next.x - current.x) / outgoing
    const outY = (next.y - current.y) / outgoing
    const beforeTurn = {
      x: current.x - inX * radius,
      y: current.y - inY * radius,
    }
    const afterTurn = {
      x: current.x + outX * radius,
      y: current.y + outY * radius,
    }

    commands.push(`L ${beforeTurn.x.toFixed(2)} ${beforeTurn.y.toFixed(2)}`)
    commands.push(
      `Q ${current.x.toFixed(2)} ${current.y.toFixed(2)} ${afterTurn.x.toFixed(2)} ${afterTurn.y.toFixed(2)}`
    )
  }

  const last = points[points.length - 1]
  commands.push(`L ${last.x.toFixed(2)} ${last.y.toFixed(2)}`)
  return commands.join(' ')
}

function formatPercent(value) {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—'
}

function formatConfidence(value) {
  return `${Math.round(Number(value || 0) * 100)}%`
}

function formatDuration(seconds) {
  const safeSeconds = Math.max(0, Number(seconds || 0))
  if (safeSeconds < 60) return `${Math.round(safeSeconds)} с`
  const minutes = Math.floor(safeSeconds / 60)
  const restSeconds = Math.round(safeSeconds % 60)
  return restSeconds > 0 ? `${minutes} мин ${restSeconds} с` : `${minutes} мин`
}

function topologyConfidenceClass(value) {
  const confidence = Number(value || 0)
  if (confidence >= 0.7) return 'strong'
  if (confidence >= 0.45) return 'medium'
  return 'weak'
}

function buildGuestName(guest) {
  return [guest.last_name, guest.first_name, guest.middle_name].filter(Boolean).join(' ')
}

function formatTime(isoString) {
  if (!isoString) return '—';
  
  const match = String(isoString).match(/(\d{2}:\d{2}:\d{2})/);
  
  if (match) {
    return match[1];
  }
  
  return isoString;
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

function startZoneHandleDrag(cameraId, pointIndex, event) {
  if (!isEditMode.value) return
  activeCameraId.value = cameraId
  if (event && typeof event.preventDefault === 'function') {
    event.preventDefault()
  }
  draggingZoneHandle.value = { cameraId, pointIndex }
}

function startZoneDrag(cameraId, event) {
  if (!isEditMode.value) return
  const camera = mappedCameras.value.find((item) => item.id === cameraId)
  const polygon = normalizeVisibilityPolygon(camera?.visibility_polygon)
  if (!camera || !polygon) return

  activeCameraId.value = cameraId
  if (event && typeof event.preventDefault === 'function') {
    event.preventDefault()
  }
  const { x, y } = getMouseNormalized(event)
  draggingZone.value = {
    cameraId,
    startX: x,
    startY: y,
    originalPolygon: polygon.map((point) => ({ ...point })),
  }
}

function resetActiveCameraZone() {
  if (!activeCamera.value) return
  activeCamera.value.visibility_polygon = buildDefaultVisibilityPolygon(activeCamera.value)
}

function clearActiveCameraZone() {
  if (!activeCamera.value) return
  activeCamera.value.visibility_polygon = null
}

function onCameraClick(camera) {
  if (isEditMode.value) {
    selectCamera(camera.id)
  } else {
    openVideoModal(camera)
  }
}

function getVideoWsUrl(cameraId) {
  return buildWsUrl(`/ws/video/${cameraId}`)
}

function openVideoModal(camera) {
  closeVideoModal()

  viewingCamera.value = camera
  displayVideoDialog.value = true
  hasVideoFrame.value = false

  nextTick().then(() => {
    if (!videoCanvas.value || !displayVideoDialog.value) {
      return
    }

    livePlayer = createCanvasStreamPlayer({
      url: getVideoWsUrl(camera.id),
      canvas: videoCanvas.value,
      onFirstFrame: () => {
        hasVideoFrame.value = true
      },
      onError: (error) => {
        console.error('[video] websocket error', error)
        ui.error('Ошибка подключения к потоку камеры')
        closeVideoModal()
      },
      onClose: (event) => {
        console.log('[video] websocket closed', event.code, event.reason)
        livePlayer = null
      },
    })
  })
}

function closeVideoModal() {
  displayVideoDialog.value = false
  viewingCamera.value = null
  hasVideoFrame.value = false

  if (livePlayer) {
    livePlayer.close()
    livePlayer = null
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
  if (!isEditMode.value) return
  if (draggingZoneHandle.value) {
    const camera = mappedCameras.value.find((item) => item.id === draggingZoneHandle.value.cameraId)
    const polygon = normalizeVisibilityPolygon(camera?.visibility_polygon)
    if (!camera || !polygon) return
    const { x, y } = getMouseNormalized(event)
    polygon[draggingZoneHandle.value.pointIndex] = { x, y }
    camera.visibility_polygon = polygon
    return
  }
  if (draggingZone.value) {
    const camera = mappedCameras.value.find((item) => item.id === draggingZone.value.cameraId)
    if (!camera) return
    const { x, y } = getMouseNormalized(event)
    const originalPolygon = draggingZone.value.originalPolygon
    const minX = Math.min(...originalPolygon.map((point) => point.x))
    const maxX = Math.max(...originalPolygon.map((point) => point.x))
    const minY = Math.min(...originalPolygon.map((point) => point.y))
    const maxY = Math.max(...originalPolygon.map((point) => point.y))
    const dx = Math.max(-minX, Math.min(1 - maxX, x - draggingZone.value.startX))
    const dy = Math.max(-minY, Math.min(1 - maxY, y - draggingZone.value.startY))

    camera.visibility_polygon = originalPolygon.map((point) => ({
      x: clamp01(point.x + dx),
      y: clamp01(point.y + dy),
    }))
    return
  }
  if (!draggingCameraId.value) return
  const camera = mappedCameras.value.find((item) => item.id === draggingCameraId.value)
  if (!camera) return

  const { x, y } = getMouseNormalized(event)
  camera.plan_x = x
  camera.plan_y = y
}

function onMapMouseUp() {
  draggingCameraId.value = null
  draggingZone.value = null
  draggingZoneHandle.value = null
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
  const placedCamera = {
    ...camera,
    plan_x: 0.5,
    plan_y: 0.5,
    visibility_polygon: null,
    building_id: Number(selectedBuildingId.value),
    floor_id: Number(selectedFloorId.value)
  }
  placedCamera.visibility_polygon = buildDefaultVisibilityPolygon(placedCamera)
  mappedCameras.value.push(placedCamera)
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
  if (!canEditPlan.value) return
  if (!selectedFloorId.value) return
  
  isEditMode.value = true
  activeCameraId.value = null
  camerasToRemoveFromFloor.value = []
  draggingCameraId.value = null
  draggingZone.value = null
  draggingZoneHandle.value = null
  
  await loadUnassignedCameras()
}

function cancelEditMode() {
  if (!canEditPlan.value) return
  isEditMode.value = false
  activeCameraId.value = null
  draggingCameraId.value = null
  draggingZone.value = null
  draggingZoneHandle.value = null
  camerasToRemoveFromFloor.value = [] 
  loadFloorContext()
}

async function savePlan() {
  if (!canEditPlan.value) return
  if (!selectedFloorId.value) return
  savingPlan.value = true
  
  try {
    const updatePromises = mappedCameras.value.map((camera) =>
      camerasApi.updateCamera(camera.id, {
        building_id: Number(currentFloor.value?.building_id) || null,
        floor_id: Number(currentFloor.value?.id) || null,
        plan_x: clamp01(typeof camera.plan_x === 'number' ? camera.plan_x : 0.5),
        plan_y: clamp01(typeof camera.plan_y === 'number' ? camera.plan_y : 0.5),
        visibility_polygon: normalizeVisibilityPolygon(camera.visibility_polygon)
      })
    )

    const removePromises = camerasToRemoveFromFloor.value.map((camId) =>
      camerasApi.updateCamera(camId, {
        building_id: null,
        floor_id: null,
        plan_x: null,
        plan_y: null,
        visibility_polygon: null
      })
    )

    await Promise.all([
      ...updatePromises,
      ...removePromises,
    ])

    isEditMode.value = false
    activeCameraId.value = null
    draggingZone.value = null
    draggingZoneHandle.value = null
    camerasToRemoveFromFloor.value = []
    
    await loadFloorContext()
    await loadGuestRoute()
    await loadUnassignedCameras() 
    
    ui.success('Положение камер и зоны видимости сохранены')
  } catch (error) {
    console.error("Ошибка сохранения плана:", error.response?.data || error)
    ui.error(ui.getErrorMessage(error, 'Не удалось сохранить позиции камер'))
  } finally {
    savingPlan.value = false
  }
}

function onPlanImageError(event) {
  event.target.style.display = 'none'
}

async function loadInitialData() {
  try {
    const [guestsRes, buildingsRes] = await Promise.all([
      guestsApi.getGuests(),
      buildingsApi.getBuildings()
    ])
    guests.value = guestsRes.data
    buildings.value = buildingsRes.data

    if (!selectedBuildingId.value && buildings.value.length > 0) {
      selectedBuildingId.value = String(buildings.value[0].id)
    } else if (selectedBuildingId.value) {
      await loadFloorsForBuilding(selectedBuildingId.value)
      await loadGuestRoute()
    }
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось загрузить данные страницы плана здания'))
  }
}

async function loadPlanAnalysis() {
  if (!selectedFloorId.value || !currentFloor.value?.has_plan) {
    return ui.warn('Сначала загрузите план этажа')
  }
  planAnalysisLoading.value = true
  try {
    const response = await floorsApi.analyzePlan(selectedFloorId.value)
    planAnalysis.value = response.data
    showPlanAnalysis.value = true
    ui.success('План проанализирован. Проверьте подсветку и разметьте зоны камер вручную.')
  } catch (error) {
    planAnalysis.value = null
    ui.error(ui.getErrorMessage(error, 'Не удалось проанализировать план этажа'))
  } finally {
    planAnalysisLoading.value = false
  }
}

async function loadGuestRoute() {
  try {
    const response = await analyticsApi.getGuestRoute({
      guestId: selectedGuestId.value,
      targetDate: routeDate.value,
      buildingId: selectedBuildingId.value,
      limit: 300,
    })
    routePoints.value = response.data
  } catch (error) {
    routePoints.value = []
    ui.error(ui.getErrorMessage(error, 'Не удалось загрузить маршрут гостя'))
  }
}

async function loadCameraTransitions() {
  if (!selectedBuildingId.value || !selectedFloorId.value) {
    cameraTransitions.value = []
    return
  }

  try {
    const response = await analyticsApi.getCameraTransitions({
      targetDate: routeDate.value,
      days: TOPOLOGY_DAYS,
      buildingId: selectedBuildingId.value,
      floorId: selectedFloorId.value,
      personType: 'all',
      maxGapMinutes: 45,
      minCount: 1,
      limit: 120,
    })
    cameraTransitions.value = response.data
  } catch (error) {
    cameraTransitions.value = []
    ui.error(ui.getErrorMessage(error, 'Не удалось загрузить связи камер'))
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
    ui.error(ui.getErrorMessage(error, 'Не удалось загрузить этажи'))
  } finally {
    floorsLoading.value = false
  }
}

async function loadFloorContext() {
  if (!selectedBuildingId.value || !selectedFloorId.value) {
    mappedCameras.value = []
    planAnalysis.value = null
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
      plan_y: typeof camera.plan_y === 'number' && camera.plan_y !== null ? camera.plan_y : 0.5,
      visibility_polygon: normalizeVisibilityPolygon(camera.visibility_polygon)
    }))
    if (!mappedCameras.value.some((item) => item.id === activeCameraId.value)) {
      activeCameraId.value = null
    }
    planVersion.value = Date.now()
  } catch (error) {
    mappedCameras.value = []
    planAnalysis.value = null
    activeCameraId.value = null
    ui.error(ui.getErrorMessage(error, 'Не удалось загрузить данные этажа'))
  }
}

function distributeFallbackX(index, total) {
  if (total <= 1) return 0.5
  return 0.15 + (0.7 / (total - 1)) * index
}

function openBuildingModal() {
  if (!canEditPlan.value) return
  buildingForm.value = { name: '', address: '' }
  buildingModalVisible.value = true
}

function closeBuildingModal() {
  buildingModalVisible.value = false
  buildingSaving.value = false
}

async function saveBuilding() {
  if (!canEditPlan.value) return
  if (!buildingForm.value.name.trim()) return ui.warn('Введите название здания')
  buildingSaving.value = true
  try {
    const response = await buildingsApi.createBuilding({
      name: buildingForm.value.name.trim(),
      address: buildingForm.value.address.trim() || null
    })
    await loadInitialData()
    selectedBuildingId.value = String(response.data.id)
    closeBuildingModal()
    ui.success('Здание создано')
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось создать здание'))
  } finally {
    buildingSaving.value = false
  }
}

function openFloorModal(editCurrent = false) {
  if (!canEditPlan.value) return
  if (!selectedBuildingId.value) return ui.warn('Сначала выберите или создайте здание')
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
  if (!canEditPlan.value) return
  if (!floorForm.value.building_id || !floorForm.value.name.trim() || floorForm.value.floor_number === '') {
    return ui.warn('Заполните обязательные поля этажа')
  }
  const isEditingFloor = Boolean(floorForm.value.id)

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
    const targetFloorId = String(response.data.id) 
    
    await loadInitialData()
    selectedBuildingId.value = targetBuildingId
    await loadFloorsForBuilding(targetBuildingId)
    
    if (selectedFloorId.value === targetFloorId) {
      await loadFloorContext()
    } else {
      selectedFloorId.value = targetFloorId
    }
    
    closeFloorModal()
    ui.success(isEditingFloor ? 'Этаж обновлён' : 'Этаж создан')
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось сохранить этаж'))
  } finally {
    floorSaving.value = false
  }
}

watch(selectedBuildingId, async (newValue) => {
  isEditMode.value = false
  activeCameraId.value = null
  mappedCameras.value = []
  floors.value = []
  selectedFloorId.value = ''
  planAnalysis.value = null
  if (!newValue) return
  await loadFloorsForBuilding(newValue)
  await loadGuestRoute()
  await loadCameraTransitions()
})

watch(selectedFloorId, async (newValue) => {
  isEditMode.value = false
  activeCameraId.value = null
  if (!newValue) {
    mappedCameras.value = []
    planAnalysis.value = null
    return
  }
  planAnalysis.value = null
  await loadFloorContext()
  await loadCameraTransitions()
})

watch([selectedGuestId, routeDate], async () => {
  await loadGuestRoute()
  await loadCameraTransitions()
})

onMounted(async () => {
  await loadInitialData()
})

onBeforeUnmount(() => {
  closeVideoModal()
})
</script>

<style scoped>
.page-container { height: 100%; display: flex; flex-direction: column; gap: 1rem; }
.header-panel, .filters-row, .map-section, .logs-section, .editor-sidebar { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04); }
.header-panel { display: flex; justify-content: space-between; align-items: flex-start; padding: 1.25rem 1.5rem; }
.page-title { font-size: 1.5rem; font-weight: 600; color: #0f172a; margin: 0; }
.page-subtitle { margin: 0.35rem 0 0; color: #64748b; font-size: 0.9rem; }
.top-buttons, .filter-actions { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
.filters-row { display: grid; grid-template-columns: minmax(190px, 1fr) minmax(190px, 1fr) minmax(190px, 1fr) minmax(150px, 0.7fr) auto; gap: 1rem; padding: 1rem 1.25rem; align-items: end; }
.filter-group { display: flex; flex-direction: column; gap: 0.4rem; }
.filter-group.compact { min-width: 150px; }
.filter-group label { font-size: 0.85rem; color: #475569; font-weight: 600; }
.form-input { width: 100%; padding: 0.7rem 0.9rem; border-radius: 8px; border: 1px solid #cbd5e1; background: #f8fafc; font-size: 0.95rem; color: #1e293b; }
.form-input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12); background: #ffffff; }

.btn-primary, .btn-secondary, .btn-success, .btn-text { border: none; border-radius: 8px; padding: 0.65rem 1rem; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 0.5rem; }
.btn-primary { background: #3b82f6; color: #ffffff; }
.btn-secondary { background: #eef2ff; color: #334155; }
.btn-success { background: #10b981; color: #ffffff; }
.btn-text { background: transparent; color: #64748b; }
.btn-primary:disabled, .btn-secondary:disabled, .btn-success:disabled, .btn-text:disabled { opacity: 0.6; cursor: not-allowed; }

.tracking-grid { 
  
  display: flex;
  flex-direction: row;
  gap: 1rem; 
  height: fit-content; 
  max-height: 800px;
  align-items: stretch; 
}

.map-section {
  flex: 2.1;
  display: flex; 
  flex-direction: column; 
  padding: 1rem;  
  min-height: 0; 
}

.logs-section, .editor-sidebar { 
  flex: 1;
  display: flex; 
  flex-direction: column; 
  padding: 1rem; 
  min-height: 0; 
}
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
.camera-pin.route-pin { background: #f59e0b; box-shadow: 0 0 0 5px rgba(245, 158, 11, 0.2); }
.camera-tooltip { display: none; position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%); background: #0f172a; color: white; padding: 0.35rem 0.55rem; border-radius: 6px; font-size: 0.75rem; white-space: nowrap; }
.camera-pin:hover .camera-tooltip { display: block; }
.route-step { position: absolute; right: -8px; top: -8px; min-width: 18px; height: 18px; padding: 0 0.25rem; border-radius: 999px; background: #ffffff; color: #92400e; border: 1px solid #fbbf24; display: inline-flex; align-items: center; justify-content: center; font-size: 0.68rem; font-weight: 800; line-height: 1; }

.topology-layer { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; }
.topology-layer marker path { fill: #0f766e; }
.topology-edge { stroke: #0f766e; stroke-width: 0.75; stroke-linecap: round; opacity: 0.72; vector-effect: non-scaling-stroke; }
.topology-edge.strong { stroke: #0f766e; opacity: 0.92; stroke-width: 1; }
.topology-edge.medium { stroke: #f59e0b; opacity: 0.78; }
.topology-edge.weak { stroke: #94a3b8; opacity: 0.58; stroke-dasharray: 3 2; }

.map-overlay-layer { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; }
.analysis-wall { stroke: #0f172a; stroke-width: 0.55; stroke-linecap: round; opacity: 0.4; vector-effect: non-scaling-stroke; }
.analysis-door { stroke: #22c55e; stroke-width: 1.1; stroke-linecap: round; opacity: 0.72; stroke-dasharray: 2 1; vector-effect: non-scaling-stroke; }
.analysis-room { fill: rgba(59, 130, 246, 0.1); stroke: rgba(37, 99, 235, 0.24); stroke-width: 0.5; vector-effect: non-scaling-stroke; }
.analysis-corridor { fill: rgba(20, 184, 166, 0.13); stroke: rgba(15, 118, 110, 0.32); stroke-width: 0.65; vector-effect: non-scaling-stroke; }
.camera-zone { fill: rgba(245, 158, 11, 0.14); stroke: rgba(217, 119, 6, 0.58); stroke-width: 0.85; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.camera-zone.active { fill: rgba(16, 185, 129, 0.18); stroke: rgba(5, 150, 105, 0.9); stroke-width: 1.1; }
.camera-zone.editable { pointer-events: all; cursor: grab; }
.camera-zone.editable:active { cursor: grabbing; }
.route-curve-line { fill: none; stroke: #f97316; stroke-width: 2.35; stroke-linecap: round; stroke-linejoin: round; opacity: 0.96; vector-effect: non-scaling-stroke; filter: drop-shadow(0 1px 2px rgba(124, 45, 18, 0.25)); }
.zone-handle { position: absolute; z-index: 4; width: 22px; height: 22px; transform: translate(-50%, -50%); border-radius: 999px; background: #ffffff; border: 2px solid #059669; color: #047857; display: flex; align-items: center; justify-content: center; font-size: 0.68rem; font-weight: 800; cursor: grab; box-shadow: 0 3px 9px rgba(15, 23, 42, 0.2); }
.zone-handle:active { cursor: grabbing; }

.pulse-ring { position: absolute; inset: -2px; border: 2px solid #10b981; border-radius: 50%; animation: pulse 1.5s infinite; }
@keyframes pulse { 0% { transform: scale(1); opacity: 1; } 100% { transform: scale(2.4); opacity: 0; } }

.logs-list { 
  margin-top: 1rem; 
  overflow-y: auto; 
  display: flex; 
  flex-direction: column; 
  gap: 0.75rem; 
  flex: 1; 
  height: 0; 
  padding-right: 0.5rem; 
}
.route-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.route-header p { margin: 0.25rem 0 0; color: #64748b; font-size: 0.85rem; }
.route-count { min-width: 34px; height: 28px; padding: 0 0.6rem; border-radius: 999px; background: #fef3c7; color: #92400e; display: inline-flex; align-items: center; justify-content: center; font-weight: 800; }
.log-card { display: flex; gap: 1rem; align-items: center; padding: 0.8rem 0.9rem; border-radius: 8px; background: #f8fafc; border: 1px solid #e2e8f0; }
.route-card { border-left: 4px solid #f59e0b; }
.log-time { font-family: monospace; font-size: 0.82rem; color: #64748b; min-width: 70px; }
.log-name { color: #0f172a; font-weight: 600; }
.log-camera { margin-top: 0.2rem; font-size: 0.82rem; color: #64748b; display: flex; align-items: center; gap: 0.3rem; }
.route-meta { margin-top: 0.2rem; color: #94a3b8; font-size: 0.78rem; }
.empty-logs, .empty-selection { margin: auto 0; text-align: center; color: #94a3b8; }

.topology-section { margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; }
.topology-header h2 { font-size: 1.05rem; }
.topology-count { background: #ccfbf1; color: #115e59; }
.topology-list { margin-top: 0.75rem; display: flex; flex-direction: column; gap: 0.55rem; max-height: 230px; overflow-y: auto; padding-right: 0.4rem; }
.transition-card { padding: 0.75rem 0.85rem; border-radius: 9px; background: #f8fafc; border: 1px solid #dbeafe; border-left: 4px solid #0f766e; }
.transition-main { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 0.5rem; color: #0f172a; font-size: 0.84rem; font-weight: 700; }
.transition-main span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.transition-main i { color: #0f766e; font-size: 0.8rem; }
.transition-meta { margin-top: 0.35rem; color: #64748b; font-size: 0.76rem; line-height: 1.35; }
.empty-topology { padding: 1rem 0.5rem; text-align: center; color: #94a3b8; font-size: 0.86rem; }

.unassigned-section { margin-bottom: 1.5rem; }
.plan-analysis-section { margin-top: 1rem; }
.plan-analysis-section h3 { font-size: 1.05rem; margin: 0 0 0.5rem 0; color: #0f172a; }
.zone-actions, .zone-editor-actions { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.65rem; }
.analysis-stats { margin-top: 0.7rem; font-size: 0.82rem; color: #64748b; font-weight: 600; }
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
.live-video-canvas { display: block; }
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
