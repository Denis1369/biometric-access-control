<template>
  <div class="page-container">
    <div class="header-panel">
      <div>
        <h1 class="page-title">План здания</h1>
        <p class="page-subtitle">Выбор здания, этажа, загрузка плана, расстановка камер и ручная разметка маршрутов.</p>
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

      <div class="filter-actions">
        <button
          v-if="canEditPlan && !isEditMode"
          class="btn-primary"
          @click="toggleEditMode"
          :disabled="!selectedFloorId"
        >
          <i class="pi pi-pencil"></i> Редактировать камеры
        </button>

        <template v-else-if="isEditMode">
          <button class="btn-text" @click="cancelEditMode">Отмена</button>
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

        <div class="route-toolbar">
          <button
            v-if="canEditPlan"
            class="mode-button"
            :class="{ active: graphMode === 'markup' }"
            :disabled="!routeGraphAvailable || isEditMode || routeGraphLoading"
            @click="setGraphMode('markup')"
          >
            Режим разметки
          </button>
          <button
            class="mode-button"
            :class="{ active: graphMode === 'path' }"
            :disabled="!routeGraphAvailable || isEditMode || routeGraphLoading"
            @click="setGraphMode('path')"
          >
            Режим маршрута
          </button>
          <button class="btn-text btn-compact" :disabled="!routePathNodes.length" @click="clearRoutePath">
            Очистить маршрут
          </button>
          <button
            v-if="canEditPlan"
            class="btn-text btn-danger btn-compact"
            :disabled="!routeNodes.length && !routeEdges.length"
            @click="confirmClearRouteGraph"
          >
            Очистить граф
          </button>
          <span class="graph-counter">
            {{ routeGraphLoading ? 'Загрузка графа...' : `Точек: ${routeNodes.length} · Линий: ${routeEdges.length}` }}
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
            ref="planImage"
            :src="currentPlanUrl"
            alt="План этажа"
            class="building-plan"
            draggable="false"
            @load="onPlanImageLoad"
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
            v-if="routeGraphAvailable"
            ref="routeSvg"
            class="route-graph-layer"
            :class="{
              'is-path-mode': graphMode === 'path',
              'is-markup-mode': graphMode === 'markup' && canEditPlan,
              'is-zone-mode': isEditingCameraZone,
            }"
            :style="planOverlayStyle"
            :viewBox="routeSvgViewBox"
            preserveAspectRatio="none"
            @pointerdown.self="onRouteSvgPointerDown"
            @pointermove="onRouteSvgPointerMove"
            @pointerup="onRouteSvgPointerUp"
            @pointerleave="cancelDraftRouteEdge"
            @contextmenu.prevent
          >
            <defs>
              <marker
                id="guest-route-arrow"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" class="guest-route-direction-arrow"></path>
              </marker>
            </defs>

            <polygon
              v-for="zone in renderedCameraZones"
              :key="`zone-${zone.camera_id}`"
              :class="[
                'camera-zone-polygon',
                { selected: zone.selected, 'guest-route-zone': zone.inGuestRoute },
              ]"
              :points="zone.pointsString"
              @pointerdown.stop="startDragSavedZone(zone, $event)"
              @click.stop="selectCamera(zone.camera_id)"
              @contextmenu.prevent.stop
            />

            <polygon
              v-if="zoneDraftPoints.length >= 2"
              class="camera-zone-polygon selected draft"
              :points="formatPolygonPoints(zoneDraftPoints)"
              @pointerdown.stop="startDragZonePolygon($event)"
            />

            <line
              v-for="edge in renderedRouteEdges"
              :key="edge.id"
              :class="['route-edge-line', { selected: selectedRouteEdgeId === edge.id }]"
              :x1="edge.from.x"
              :y1="edge.from.y"
              :x2="edge.to.x"
              :y2="edge.to.y"
              vector-effect="non-scaling-stroke"
              @pointerdown.stop
              @pointerup.stop="onRouteEdgePointerUp(edge, $event)"
              @click.stop="onRouteEdgeClick(edge, $event)"
              @contextmenu.prevent.stop="deleteRouteEdge(edge.id)"
            />

            <polyline
              v-if="routePathPolyline"
              class="route-path-line"
              :points="routePathPolyline"
              fill="none"
              vector-effect="non-scaling-stroke"
            />

            <polyline
              v-if="guestRoutePolyline"
              class="guest-probable-route-line"
              :points="guestRoutePolyline"
              fill="none"
              vector-effect="non-scaling-stroke"
              marker-mid="url(#guest-route-arrow)"
              marker-end="url(#guest-route-arrow)"
            />

            <g
              v-for="marker in guestRouteEventMarkers"
              :key="marker.id"
              class="guest-route-event-marker"
            >
              <circle :cx="marker.x" :cy="marker.y" :r="routeNodeRadius * 1.25" vector-effect="non-scaling-stroke" />
              <text :x="marker.x" :y="marker.y" text-anchor="middle" dominant-baseline="central">
                {{ marker.order }}
              </text>
            </g>

            <line
              v-if="draftRouteEdge"
              class="route-edge-draft"
              :x1="draftRouteEdge.fromX"
              :y1="draftRouteEdge.fromY"
              :x2="draftRouteEdge.toX"
              :y2="draftRouteEdge.toY"
              vector-effect="non-scaling-stroke"
            />

            <circle
              v-for="node in routeNodes"
              :key="node.id"
              :class="[
                'route-node',
                {
                  'route-start-node': routeStartNodeId === node.id,
                  'route-end-node': routeEndNodeId === node.id,
                },
              ]"
              :cx="node.x"
              :cy="node.y"
              :r="routeNodeRadius"
              vector-effect="non-scaling-stroke"
              @pointerdown.stop="onRouteNodePointerDown(node, $event)"
              @pointerup.stop="onRouteNodePointerUp(node, $event)"
              @click.stop="onRouteNodeClick(node)"
              @contextmenu.prevent.stop="deleteRouteNode(node.id)"
            />

            <circle
              v-for="(point, index) in editableZonePoints"
              v-show="isEditingCameraZone"
              :key="`zone-point-${index}`"
              class="camera-zone-point"
              :cx="point.x"
              :cy="point.y"
              :r="routeNodeRadius * 0.7"
              vector-effect="non-scaling-stroke"
              @pointerdown.stop="startDragZonePoint(index, $event)"
              @pointerup.stop="finishZoneDrag"
              @contextmenu.prevent.stop="resetActiveZoneDraft"
            />
          </svg>

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
            <span v-if="cameraZonesByCameraId.has(camera.id)" class="camera-zone-indicator"></span>
            <span class="pulse-ring" v-if="!isEditMode && activeCameraId === camera.id"></span>
            <div class="camera-tooltip">{{ camera.name }}</div>
          </div>
        </div>
      </div>

      <div class="logs-section" v-if="!isEditMode">
        <div class="section-header">
          <div>
            <h2>Камеры этажа</h2>
            <p>{{ selectedFloorLabel || 'Этаж не выбран' }}</p>
          </div>
          <span class="item-count">{{ mappedCameras.length }}</span>
        </div>

        <div class="logs-list">
          <div
            v-for="camera in mappedCameras"
            :key="camera.id"
            :class="['camera-card', { selected: activeCameraId === camera.id }]"
            @click="onCameraCardClick(camera)"
          >
            <div class="camera-card-icon">
              <i class="pi pi-video"></i>
            </div>
            <div class="camera-card-info">
              <div class="camera-card-name">{{ camera.name }}</div>
              <div class="camera-card-meta">
                X: {{ formatPercent(camera.plan_x) }} · Y: {{ formatPercent(camera.plan_y) }}
              </div>
              <div v-if="cameraZonesByCameraId.has(camera.id)" class="camera-card-meta zone-ready">
                Зона видимости задана
              </div>
            </div>
          </div>
          <div v-if="mappedCameras.length === 0" class="empty-logs">
            На выбранном этаже камеры пока не размещены.
          </div>
        </div>

        <div class="side-panel">
          <h3>Маршрут гостя</h3>
          <div class="form-group compact-form">
            <label>Гость</label>
            <select v-model="selectedGuestId" class="form-input">
              <option value="">Выберите гостя...</option>
              <option v-for="guest in guests" :key="guest.id" :value="String(guest.id)">
                {{ formatGuestName(guest) }}
              </option>
            </select>
          </div>
          <div class="form-group compact-form">
            <label>Дата/время от</label>
            <input v-model="guestRouteTimeFrom" class="form-input" type="datetime-local" />
          </div>
          <div class="form-group compact-form">
            <label>Дата/время до</label>
            <input v-model="guestRouteTimeTo" class="form-input" type="datetime-local" />
          </div>
          <div class="zone-actions">
            <button class="btn-primary btn-sm" :disabled="guestRouteLoading || !selectedGuestId || !selectedFloorId" @click="buildGuestRoute">
              {{ guestRouteLoading ? 'Построение...' : 'Построить маршрут гостя' }}
            </button>
            <button class="btn-text btn-sm" :disabled="!guestProbableRoute" @click="clearGuestRoute">
              Очистить маршрут гостя
            </button>
          </div>

          <div v-if="guestRouteWarnings.length" class="camera-zone-warning">
            <div v-for="warning in guestRouteWarnings" :key="warning">{{ warning }}</div>
          </div>

          <div v-if="guestRouteEvents.length" class="guest-route-events">
            <div v-for="(event, index) in guestRouteEvents" :key="`${event.source}-${event.tracking_log_id || event.access_log_id || index}`" class="guest-route-event-row">
              <span class="event-order">{{ index + 1 }}</span>
              <div>
                <div class="camera-card-name">{{ event.camera_name || `Камера ${event.camera_id}` }}</div>
                <div class="camera-card-meta">{{ formatTimestamp(event.timestamp) }}</div>
              </div>
            </div>
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

          <div class="side-panel zone-editor-box">
            <h3>Зона видимости камеры</h3>
            <p class="instruction-small">
              Нажмите «Задать зону», кликните 4 точки на плане. Вершины и весь полигон можно перетаскивать.
            </p>
            <div class="camera-card-meta">
              {{ selectedCameraHasZone ? 'Зона сохранена' : 'Зона пока не задана' }}
              <span v-if="zoneDraftCameraId === activeCamera.id">
                · выбрано точек: {{ zoneDraftPoints.length }}/4
              </span>
            </div>
            <div class="zone-actions">
              <button class="btn-secondary btn-sm" @click="startZoneDraft">
                {{ selectedCameraHasZone ? 'Редактировать зону' : 'Задать зону' }}
              </button>
              <button class="btn-success btn-sm" :disabled="zoneSaving || editableZonePoints.length !== 4" @click="saveActiveCameraZone">
                Сохранить зону
              </button>
              <button class="btn-text btn-danger btn-sm" :disabled="!editableZonePoints.length" @click="resetActiveZoneDraft">
                Сбросить
              </button>
              <button class="btn-text btn-danger btn-sm" :disabled="!selectedCameraHasZone" @click="deleteActiveCameraZone">
                Удалить зону
              </button>
            </div>
          </div>
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { buildingsApi } from '../api/buildings'
import { buildWsUrl } from '../api/client'
import { cameraVisibilityApi } from '../api/cameraVisibility'
import { camerasApi } from '../api/cameras'
import { floorsApi } from '../api/floors'
import { guestsApi } from '../api/guests'
import { guestRoutesApi } from '../api/guestRoutes'
import { routeGraphApi } from '../api/routeGraph'
import { formatPolygonPoints, polygonCentroid } from '../services/geometry'
import { createCanvasStreamPlayer } from '../services/liveStream'
import { useAuth } from '../services/auth'
import { useUi } from '../services/ui'

defineOptions({ name: 'TrackingPage' })

const auth = useAuth()
const ui = useUi()
const canEditPlan = computed(() => auth.hasAnyRole('super_admin'))

const buildings = ref([])
const floors = ref([])
const mappedCameras = ref([])
const unassignedCameras = ref([])
const camerasToRemoveFromFloor = ref([])

const selectedBuildingId = ref('')
const selectedFloorId = ref('')
const activeCameraId = ref(null)

const isEditMode = ref(false)
const mapContainer = ref(null)
const planImage = ref(null)
const routeSvg = ref(null)
const draggingCameraId = ref(null)
const savingPlan = ref(false)
const floorsLoading = ref(false)
const planVersion = ref(Date.now())

const graphMode = ref('markup')
const routeNodes = ref([])
const routeEdges = ref([])
const routePathNodes = ref([])
const routeStartNodeId = ref(null)
const routeEndNodeId = ref(null)
const selectedRouteEdgeId = ref(null)
const draftRouteEdge = ref(null)
const routeGraphLoading = ref(false)
const cameraZones = ref([])
const zoneDraftPoints = ref([])
const zoneDraftCameraId = ref(null)
const draggingZonePointIndex = ref(null)
const draggingZonePolygon = ref(null)
const zoneSaving = ref(false)
const guests = ref([])
const selectedGuestId = ref('')
const guestRouteTimeFrom = ref('')
const guestRouteTimeTo = ref('')
const guestRouteLoading = ref(false)
const guestProbableRoute = ref(null)
const planImageMetrics = ref({
  naturalWidth: 1,
  naturalHeight: 1,
  left: 0,
  top: 0,
  width: 0,
  height: 0,
})

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
let planResizeObserver = null
let suppressNextRouteEdgeClick = false

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
const routeGraphAvailable = computed(() => Boolean(selectedFloorId.value && currentFloor.value?.has_plan))
const routeSvgViewBox = computed(() => {
  const { naturalWidth, naturalHeight } = planImageMetrics.value
  return `0 0 ${naturalWidth || 1} ${naturalHeight || 1}`
})
const planOverlayStyle = computed(() => {
  const { left, top, width, height } = planImageMetrics.value
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    height: `${height}px`,
  }
})
const routeNodeRadius = computed(() => Math.max(8, planImageMetrics.value.naturalWidth / 120))
const routeNodesById = computed(() => new Map(routeNodes.value.map((node) => [node.id, node])))
const renderedRouteEdges = computed(() =>
  routeEdges.value
    .map((edge) => ({
      ...edge,
      from: routeNodesById.value.get(edge.from_node_id),
      to: routeNodesById.value.get(edge.to_node_id),
    }))
    .filter((edge) => edge.from && edge.to)
)
const routePathPolyline = computed(() =>
  routePathNodes.value.map((node) => `${node.x},${node.y}`).join(' ')
)
const cameraZonesByCameraId = computed(() => new Map(cameraZones.value.map((zone) => [zone.camera_id, zone])))
const activeCameraZone = computed(() =>
  activeCameraId.value ? cameraZonesByCameraId.value.get(activeCameraId.value) || null : null
)
const isEditingCameraZone = computed(() =>
  Boolean(isEditMode.value && canEditPlan.value && activeCameraId.value && zoneDraftCameraId.value === activeCameraId.value)
)
const editableZonePoints = computed(() => {
  if (zoneDraftCameraId.value === activeCameraId.value) {
    return zoneDraftPoints.value
  }
  return activeCameraZone.value?.points || []
})
const renderedCameraZones = computed(() =>
  cameraZones.value
    .filter((zone) => zoneDraftCameraId.value !== zone.camera_id)
    .map((zone) => ({
      ...zone,
      pointsString: formatPolygonPoints(zone.points),
      centroid: polygonCentroid(zone.points),
      selected: zone.camera_id === activeCameraId.value,
      inGuestRoute: Boolean(
        guestProbableRoute.value?.camera_zones?.some((routeZone) => routeZone.camera_id === zone.camera_id)
      ),
    }))
)
const selectedCameraHasZone = computed(() => Boolean(activeCameraZone.value))
const guestRoutePolyline = computed(() =>
  (guestProbableRoute.value?.route_nodes || []).map((node) => `${node.x},${node.y}`).join(' ')
)
const guestRouteEvents = computed(() => guestProbableRoute.value?.events || [])
const guestRouteWarnings = computed(() => guestProbableRoute.value?.warnings || [])
const guestRouteEventMarkers = computed(() =>
  guestRouteEvents.value
    .map((event, index) => {
      const zone = cameraZonesByCameraId.value.get(event.camera_id)
      const points = zone?.points || guestProbableRoute.value?.camera_zones?.find((item) => item.camera_id === event.camera_id)?.points
      if (!points?.length) return null
      return {
        ...polygonCentroid(points),
        id: `${event.source}-${event.tracking_log_id || event.access_log_id || index}`,
        order: index + 1,
        camera_id: event.camera_id,
      }
    })
    .filter(Boolean)
)

function clamp01(value) {
  return Math.max(0, Math.min(1, value))
}

function formatPercent(value) {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—'
}

function cameraStyle(camera) {
  const x = typeof camera.plan_x === 'number' ? camera.plan_x : 0.5
  const y = typeof camera.plan_y === 'number' ? camera.plan_y : 0.5
  return { left: `${x * 100}%`, top: `${y * 100}%` }
}

function getMouseNormalized(event) {
  if (!mapContainer.value) return { x: 0.5, y: 0.5 }
  const rect = mapContainer.value.getBoundingClientRect()
  return {
    x: clamp01((event.clientX - rect.left) / rect.width),
    y: clamp01((event.clientY - rect.top) / rect.height),
  }
}

function updatePlanImageMetrics() {
  if (!mapContainer.value || !planImage.value?.naturalWidth || !planImage.value?.naturalHeight) return

  const containerRect = mapContainer.value.getBoundingClientRect()
  const naturalWidth = planImage.value.naturalWidth
  const naturalHeight = planImage.value.naturalHeight
  const scale = Math.min(containerRect.width / naturalWidth, containerRect.height / naturalHeight)
  const width = naturalWidth * scale
  const height = naturalHeight * scale

  planImageMetrics.value = {
    naturalWidth,
    naturalHeight,
    left: (containerRect.width - width) / 2,
    top: (containerRect.height - height) / 2,
    width,
    height,
  }
}

function onPlanImageLoad() {
  updatePlanImageMetrics()
}

function getRoutePointerOriginal(event) {
  if (!routeSvg.value) return null
  const rect = routeSvg.value.getBoundingClientRect()
  if (!rect.width || !rect.height) return null

  const { naturalWidth, naturalHeight } = planImageMetrics.value
  return {
    x: clamp01((event.clientX - rect.left) / rect.width) * naturalWidth,
    y: clamp01((event.clientY - rect.top) / rect.height) * naturalHeight,
  }
}

function projectPointToSegment(point, from, to) {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const lengthSquared = dx * dx + dy * dy
  if (!lengthSquared) return { ...from }

  const t = clamp01(((point.x - from.x) * dx + (point.y - from.y) * dy) / lengthSquared)
  return {
    x: from.x + t * dx,
    y: from.y + t * dy,
  }
}

function getPointOnRouteEdge(edge, point) {
  const from = edge.from || routeNodesById.value.get(edge.from_node_id)
  const to = edge.to || routeNodesById.value.get(edge.to_node_id)
  if (!from || !to) return point
  return projectPointToSegment(point, from, to)
}

function resetRouteSelection() {
  routeStartNodeId.value = null
  routeEndNodeId.value = null
  routePathNodes.value = []
}

function clearRouteGraphState() {
  routeNodes.value = []
  routeEdges.value = []
  selectedRouteEdgeId.value = null
  draftRouteEdge.value = null
  resetRouteSelection()
}

function clearCameraZonesState() {
  cameraZones.value = []
  zoneDraftPoints.value = []
  zoneDraftCameraId.value = null
  draggingZonePointIndex.value = null
  draggingZonePolygon.value = null
}

function clearGuestRoute() {
  guestProbableRoute.value = null
}

function distributeFallbackX(index, total) {
  if (total <= 1) return 0.5
  return 0.15 + (0.7 / (total - 1)) * index
}

function selectCamera(id) {
  if (activeCameraId.value === id) return
  activeCameraId.value = id
  zoneDraftPoints.value = []
  zoneDraftCameraId.value = null
}

function onCameraClick(camera) {
  if (isEditMode.value) {
    selectCamera(camera.id)
  } else {
    openVideoModal(camera)
  }
}

function onCameraCardClick(camera) {
  openVideoModal(camera)
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
    if (!videoCanvas.value || !displayVideoDialog.value) return

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
      onClose: () => {
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
  if (event && typeof event.preventDefault === 'function') event.preventDefault()
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
    unassignedCameras.value = response.data.filter((camera) => !camera.floor_id)
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
    floor_id: Number(selectedFloorId.value),
  })
  unassignedCameras.value = unassignedCameras.value.filter((item) => item.id !== camera.id)
  activeCameraId.value = camera.id
}

function removeCameraFromFloor(id) {
  const cameraIndex = mappedCameras.value.findIndex((camera) => camera.id === id)
  if (cameraIndex < 0) return

  const camera = mappedCameras.value[cameraIndex]
  mappedCameras.value.splice(cameraIndex, 1)
  unassignedCameras.value.push(camera)
  camerasToRemoveFromFloor.value.push(camera.id)
  if (activeCameraId.value === id) activeCameraId.value = null
}

async function toggleEditMode() {
  if (!canEditPlan.value || !selectedFloorId.value) return

  isEditMode.value = true
  activeCameraId.value = null
  zoneDraftPoints.value = []
  zoneDraftCameraId.value = null
  draggingZonePointIndex.value = null
  draggingZonePolygon.value = null
  camerasToRemoveFromFloor.value = []
  draggingCameraId.value = null
  await loadUnassignedCameras()
}

function cancelEditMode() {
  if (!canEditPlan.value) return
  isEditMode.value = false
  activeCameraId.value = null
  draggingCameraId.value = null
  zoneDraftPoints.value = []
  zoneDraftCameraId.value = null
  draggingZonePointIndex.value = null
  draggingZonePolygon.value = null
  camerasToRemoveFromFloor.value = []
  loadFloorContext()
}

async function savePlan() {
  if (!canEditPlan.value || !selectedFloorId.value) return
  savingPlan.value = true

  try {
    const updatePromises = mappedCameras.value.map((camera) =>
      camerasApi.updateCamera(camera.id, {
        building_id: Number(currentFloor.value?.building_id) || null,
        floor_id: Number(currentFloor.value?.id) || null,
        plan_x: clamp01(typeof camera.plan_x === 'number' ? camera.plan_x : 0.5),
        plan_y: clamp01(typeof camera.plan_y === 'number' ? camera.plan_y : 0.5),
      })
    )

    const removePromises = camerasToRemoveFromFloor.value.map((cameraId) =>
      camerasApi.updateCamera(cameraId, {
        building_id: null,
        floor_id: null,
        plan_x: null,
        plan_y: null,
      })
    )

    await Promise.all([...updatePromises, ...removePromises])

    isEditMode.value = false
    activeCameraId.value = null
    draggingCameraId.value = null
    zoneDraftPoints.value = []
    zoneDraftCameraId.value = null
    draggingZonePointIndex.value = null
    draggingZonePolygon.value = null
    camerasToRemoveFromFloor.value = []

    await loadFloorContext()
    await loadUnassignedCameras()

    ui.success('Положение камер успешно сохранено')
  } catch (error) {
    console.error('Ошибка сохранения плана:', error.response?.data || error)
    ui.error(ui.getErrorMessage(error, 'Не удалось сохранить позиции камер'))
  } finally {
    savingPlan.value = false
  }
}

function setGraphMode(mode) {
  if (!routeGraphAvailable.value || isEditMode.value) return
  if (mode === 'markup' && !canEditPlan.value) return
  graphMode.value = mode
  draftRouteEdge.value = null
  selectedRouteEdgeId.value = null
  draggingZonePointIndex.value = null
}

async function loadRouteGraph() {
  if (!selectedFloorId.value) {
    clearRouteGraphState()
    return
  }

  routeGraphLoading.value = true
  try {
    const response = await routeGraphApi.getGraph(selectedFloorId.value)
    routeNodes.value = response.data.nodes || []
    routeEdges.value = response.data.edges || []
    selectedRouteEdgeId.value = null
    draftRouteEdge.value = null
    resetRouteSelection()
  } catch (error) {
    clearRouteGraphState()
    ui.error(ui.getErrorMessage(error, 'Не удалось загрузить граф маршрутов этажа'))
  } finally {
    routeGraphLoading.value = false
  }
}

async function loadCameraZones() {
  if (!selectedFloorId.value) {
    clearCameraZonesState()
    return
  }

  try {
    const response = await cameraVisibilityApi.getFloorZones(selectedFloorId.value)
    cameraZones.value = response.data.zones || []
    zoneDraftPoints.value = []
    zoneDraftCameraId.value = null
  } catch (error) {
    clearCameraZonesState()
    ui.error(ui.getErrorMessage(error, 'Не удалось загрузить зоны видимости камер'))
  }
}

function startZoneDraft() {
  if (!activeCamera.value) return ui.warn('Сначала выберите камеру')
  if (!isEditMode.value) return ui.warn('Включите режим редактирования камер')
  zoneDraftCameraId.value = activeCamera.value.id
  zoneDraftPoints.value = activeCameraZone.value?.points?.map((point) => ({ ...point })) || []
  draggingZonePolygon.value = null
}

function addZoneDraftPoint(event) {
  if (!isEditingCameraZone.value || !activeCamera.value) return
  if (event.button !== 0) return
  if (zoneDraftPoints.value.length >= 4) return

  const point = getRoutePointerOriginal(event)
  if (!point) return
  zoneDraftPoints.value.push(point)
}

function startDragZonePoint(index, event) {
  if (!isEditingCameraZone.value || !activeCamera.value) return
  if (event.button !== 0) return
  draggingZonePolygon.value = null
  draggingZonePointIndex.value = index
}

function moveZonePoint(event) {
  const point = getRoutePointerOriginal(event)
  if (!point || draggingZonePointIndex.value === null) return
  zoneDraftPoints.value[draggingZonePointIndex.value] = point
}

function startDragSavedZone(zone, event) {
  if (!canEditPlan.value || !isEditMode.value) return
  if (event.button !== 0) return
  if (activeCameraId.value !== zone.camera_id) {
    activeCameraId.value = zone.camera_id
  }
  zoneDraftCameraId.value = zone.camera_id
  zoneDraftPoints.value = zone.points.map((point) => ({ ...point }))
  startDragZonePolygon(event)
}

function startDragZonePolygon(event) {
  if (!isEditingCameraZone.value || !activeCamera.value) return
  if (event.button !== 0 || zoneDraftPoints.value.length < 3) return

  const startPoint = getRoutePointerOriginal(event)
  if (!startPoint) return

  event.preventDefault()
  draggingZonePointIndex.value = null
  draggingZonePolygon.value = {
    startPoint,
    originalPoints: zoneDraftPoints.value.map((point) => ({ ...point })),
  }
}

function moveZonePolygon(event) {
  if (!draggingZonePolygon.value) return
  const point = getRoutePointerOriginal(event)
  if (!point) return

  const { naturalWidth, naturalHeight } = planImageMetrics.value
  const originalPoints = draggingZonePolygon.value.originalPoints
  const minX = Math.min(...originalPoints.map((item) => item.x))
  const maxX = Math.max(...originalPoints.map((item) => item.x))
  const minY = Math.min(...originalPoints.map((item) => item.y))
  const maxY = Math.max(...originalPoints.map((item) => item.y))

  const rawDx = point.x - draggingZonePolygon.value.startPoint.x
  const rawDy = point.y - draggingZonePolygon.value.startPoint.y
  const dx = Math.max(-minX, Math.min((naturalWidth || maxX) - maxX, rawDx))
  const dy = Math.max(-minY, Math.min((naturalHeight || maxY) - maxY, rawDy))

  zoneDraftPoints.value = originalPoints.map((item) => ({
    x: item.x + dx,
    y: item.y + dy,
  }))
}

function finishZoneDrag() {
  draggingZonePointIndex.value = null
  draggingZonePolygon.value = null
}

function resetActiveZoneDraft() {
  if (!activeCamera.value) return
  zoneDraftCameraId.value = activeCamera.value.id
  zoneDraftPoints.value = []
  draggingZonePointIndex.value = null
  draggingZonePolygon.value = null
}

async function saveActiveCameraZone() {
  if (!activeCamera.value || !selectedFloorId.value) return
  if (editableZonePoints.value.length !== 4) return ui.warn('Зона видимости должна содержать ровно 4 точки')

  zoneSaving.value = true
  try {
    const response = await cameraVisibilityApi.saveCameraZone(activeCamera.value.id, {
      floor_id: Number(selectedFloorId.value),
      points: editableZonePoints.value,
    })
    const nextZone = response.data
    const existingIndex = cameraZones.value.findIndex((zone) => zone.camera_id === nextZone.camera_id)
    if (existingIndex >= 0) {
      cameraZones.value[existingIndex] = nextZone
    } else {
      cameraZones.value.push(nextZone)
    }
    zoneDraftPoints.value = []
    zoneDraftCameraId.value = null
    draggingZonePointIndex.value = null
    draggingZonePolygon.value = null
    clearGuestRoute()
    ui.success('Зона видимости камеры сохранена')
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось сохранить зону видимости камеры'))
  } finally {
    zoneSaving.value = false
  }
}

async function deleteActiveCameraZone() {
  if (!activeCamera.value) return
  const confirmed = await ui.confirm({
    header: 'Удалить зону видимости?',
    message: `Зона камеры «${activeCamera.value.name}» будет удалена.`,
    acceptLabel: 'Удалить',
    acceptSeverity: 'danger',
  })
  if (!confirmed) return

  try {
    await cameraVisibilityApi.deleteCameraZone(activeCamera.value.id)
    cameraZones.value = cameraZones.value.filter((zone) => zone.camera_id !== activeCamera.value.id)
    zoneDraftPoints.value = []
    zoneDraftCameraId.value = null
    draggingZonePointIndex.value = null
    draggingZonePolygon.value = null
    clearGuestRoute()
    ui.success('Зона видимости камеры удалена')
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось удалить зону видимости камеры'))
  }
}

async function loadGuests() {
  try {
    const response = await guestsApi.getGuests()
    guests.value = response.data || []
  } catch (error) {
    guests.value = []
    ui.error(ui.getErrorMessage(error, 'Не удалось загрузить список гостей'))
  }
}

function formatGuestName(guest) {
  return [guest.last_name, guest.first_name, guest.middle_name].filter(Boolean).join(' ') || `Гость ${guest.id}`
}

function formatTimestamp(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ru-RU')
}

async function buildGuestRoute() {
  if (!selectedFloorId.value) return ui.warn('Выберите этаж')
  if (!selectedGuestId.value) return ui.warn('Выберите гостя')

  guestRouteLoading.value = true
  try {
    const response = await guestRoutesApi.getGuestProbableRoute(selectedFloorId.value, selectedGuestId.value, {
      time_from: guestRouteTimeFrom.value,
      time_to: guestRouteTimeTo.value,
    })
    guestProbableRoute.value = response.data
    if (!response.data.events?.length) {
      ui.warn('За выбранный период событий не найдено')
    } else if ((response.data.warnings || []).length) {
      ui.warn('Маршрут построен с предупреждениями')
    } else {
      ui.success('Вероятный маршрут гостя построен')
    }
  } catch (error) {
    guestProbableRoute.value = null
    ui.error(ui.getErrorMessage(error, 'Не удалось построить вероятный маршрут гостя'))
  } finally {
    guestRouteLoading.value = false
  }
}

async function createRouteNodeAt(event) {
  if (!canEditPlan.value || graphMode.value !== 'markup' || isEditMode.value || !selectedFloorId.value) return
  if (event.button !== 0) return

  const point = getRoutePointerOriginal(event)
  if (!point) return

  await createRouteNodeFromPoint(point)
}

async function createRouteNodeFromPoint(point, { resetPath = true } = {}) {
  try {
    const response = await routeGraphApi.createNode(selectedFloorId.value, point)
    const node = response.data
    routeNodes.value.push(node)
    if (resetPath) resetRouteSelection()
    return node
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось создать точку маршрута'))
    return null
  }
}

function onRouteSvgPointerDown(event) {
  if (isEditingCameraZone.value) {
    addZoneDraftPoint(event)
    return
  }
  void createRouteNodeAt(event)
}

function onRouteNodePointerDown(node, event) {
  if (!canEditPlan.value || graphMode.value !== 'markup' || isEditMode.value) return
  if (event.button !== 0) return

  event.preventDefault()
  selectedRouteEdgeId.value = null
  draftRouteEdge.value = {
    fromNodeId: node.id,
    fromX: node.x,
    fromY: node.y,
    toX: node.x,
    toY: node.y,
  }
}

function onRouteSvgPointerMove(event) {
  if (draggingZonePolygon.value) {
    moveZonePolygon(event)
    return
  }

  if (draggingZonePointIndex.value !== null) {
    moveZonePoint(event)
    return
  }

  if (!draftRouteEdge.value) return
  const point = getRoutePointerOriginal(event)
  if (!point) return

  draftRouteEdge.value = {
    ...draftRouteEdge.value,
    toX: point.x,
    toY: point.y,
  }
}

function cancelDraftRouteEdge() {
  draftRouteEdge.value = null
  draggingZonePointIndex.value = null
  draggingZonePolygon.value = null
}

async function onRouteSvgPointerUp(event) {
  if (draggingZonePolygon.value) {
    draggingZonePolygon.value = null
    return
  }

  if (draggingZonePointIndex.value !== null) {
    draggingZonePointIndex.value = null
    return
  }

  const draft = draftRouteEdge.value
  if (!draft) return
  draftRouteEdge.value = null
  if (event.button !== 0) return

  const point = getRoutePointerOriginal(event)
  if (!point) return

  const targetNode = await createRouteNodeFromPoint(point, { resetPath: false })
  if (!targetNode) return

  await createRouteEdgeBetween(draft.fromNodeId, targetNode.id, { rollbackNodeId: targetNode.id })
}

function onRouteNodePointerUp(node, event) {
  if (!draftRouteEdge.value || event.button !== 0) return
  void finishRouteEdgeDrag(node)
}

function onRouteEdgePointerUp(edge, event) {
  const draft = draftRouteEdge.value
  if (!draft || event.button !== 0) return

  event.preventDefault()
  suppressNextRouteEdgeClick = true
  draftRouteEdge.value = null

  const point = getRoutePointerOriginal(event)
  if (!point) return

  void splitRouteEdgeAtPoint(edge, point, { connectFromNodeId: draft.fromNodeId })
}

function onRouteEdgeClick(edge, event) {
  if (suppressNextRouteEdgeClick) {
    suppressNextRouteEdgeClick = false
    return
  }

  if (canEditPlan.value && graphMode.value === 'markup' && !isEditMode.value) {
    void splitRouteEdgeAtPointer(edge, event)
    return
  }

  selectRouteEdge(edge.id)
}

async function finishRouteEdgeDrag(targetNode) {
  const draft = draftRouteEdge.value
  draftRouteEdge.value = null
  if (!draft || !targetNode || draft.fromNodeId === targetNode.id) return

  await createRouteEdgeBetween(draft.fromNodeId, targetNode.id)
}

async function persistRouteEdge(fromNodeId, toNodeId, isBidirectional = true) {
  const response = await routeGraphApi.createEdge(selectedFloorId.value, {
    from_node_id: fromNodeId,
    to_node_id: toNodeId,
    is_bidirectional: isBidirectional,
  })
  return response.data
}

function upsertRouteEdge(nextEdge) {
  const existingIndex = routeEdges.value.findIndex((edge) => edge.id === nextEdge.id)
  if (existingIndex >= 0) {
    routeEdges.value[existingIndex] = nextEdge
  } else {
    routeEdges.value.push(nextEdge)
  }
}

async function createRouteEdgeBetween(fromNodeId, toNodeId, { rollbackNodeId = null } = {}) {
  try {
    const nextEdge = await persistRouteEdge(fromNodeId, toNodeId)
    upsertRouteEdge(nextEdge)
    resetRouteSelection()
  } catch (error) {
    if (rollbackNodeId) {
      try {
        await routeGraphApi.deleteNode(rollbackNodeId)
        routeNodes.value = routeNodes.value.filter((node) => node.id !== rollbackNodeId)
      } catch (rollbackError) {
        console.error('Не удалось откатить точку после ошибки создания линии:', rollbackError)
      }
    }
    ui.error(ui.getErrorMessage(error, 'Не удалось создать линию маршрута'))
  }
}

async function splitRouteEdgeAtPointer(edge, event) {
  const point = getRoutePointerOriginal(event)
  if (!point) return
  await splitRouteEdgeAtPoint(edge, point)
}

async function splitRouteEdgeAtPoint(edge, point, { connectFromNodeId = null } = {}) {
  if (!canEditPlan.value || graphMode.value !== 'markup' || isEditMode.value || !selectedFloorId.value) return
  if (!edge?.id) return

  const splitPoint = getPointOnRouteEdge(edge, point)
  const newNode = await createRouteNodeFromPoint(splitPoint, { resetPath: false })
  if (!newNode) return

  const createdEdges = []
  try {
    createdEdges.push(await persistRouteEdge(edge.from_node_id, newNode.id, edge.is_bidirectional))
    createdEdges.push(await persistRouteEdge(newNode.id, edge.to_node_id, edge.is_bidirectional))

    const splitAlreadyConnects =
      connectFromNodeId === null ||
      connectFromNodeId === edge.from_node_id ||
      (connectFromNodeId === edge.to_node_id && edge.is_bidirectional)

    if (!splitAlreadyConnects) {
      createdEdges.push(await persistRouteEdge(connectFromNodeId, newNode.id, true))
    }

    await routeGraphApi.deleteEdge(edge.id)
    routeEdges.value = routeEdges.value.filter((item) => item.id !== edge.id)
    createdEdges.forEach(upsertRouteEdge)
    selectedRouteEdgeId.value = null
    resetRouteSelection()
  } catch (error) {
    try {
      await routeGraphApi.deleteNode(newNode.id)
      routeNodes.value = routeNodes.value.filter((node) => node.id !== newNode.id)
    } catch (rollbackError) {
      console.error('Не удалось откатить точку после ошибки разбиения линии:', rollbackError)
    }

    await loadRouteGraph()
    ui.error(ui.getErrorMessage(error, 'Не удалось вставить точку в линию маршрута'))
  }
}

function selectRouteEdge(edgeId) {
  selectedRouteEdgeId.value = edgeId
}

async function deleteRouteNode(nodeId) {
  if (!canEditPlan.value) return

  try {
    await routeGraphApi.deleteNode(nodeId)
    routeNodes.value = routeNodes.value.filter((node) => node.id !== nodeId)
    routeEdges.value = routeEdges.value.filter(
      (edge) => edge.from_node_id !== nodeId && edge.to_node_id !== nodeId
    )
    if (routeStartNodeId.value === nodeId || routeEndNodeId.value === nodeId) {
      resetRouteSelection()
    }
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось удалить точку маршрута'))
  }
}

async function deleteRouteEdge(edgeId) {
  if (!canEditPlan.value) return

  try {
    await routeGraphApi.deleteEdge(edgeId)
    routeEdges.value = routeEdges.value.filter((edge) => edge.id !== edgeId)
    if (selectedRouteEdgeId.value === edgeId) selectedRouteEdgeId.value = null
    resetRouteSelection()
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось удалить линию маршрута'))
  }
}

function clearRoutePath() {
  resetRouteSelection()
}

async function confirmClearRouteGraph() {
  if (!canEditPlan.value || !selectedFloorId.value) return
  const confirmed = await ui.confirm({
    header: 'Очистить граф маршрутов?',
    message: 'Все точки и линии на выбранном этаже будут удалены. Камеры и план этажа останутся без изменений.',
    acceptLabel: 'Очистить граф',
    acceptSeverity: 'danger',
  })
  if (!confirmed) return

  try {
    await routeGraphApi.clearGraph(selectedFloorId.value)
    clearRouteGraphState()
    ui.success('Граф маршрутов этажа очищен')
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось очистить граф маршрутов'))
  }
}

async function onRouteNodeClick(node) {
  if (graphMode.value !== 'path' || isEditMode.value) return
  selectedRouteEdgeId.value = null

  if (!routeStartNodeId.value || routeEndNodeId.value) {
    routeStartNodeId.value = node.id
    routeEndNodeId.value = null
    routePathNodes.value = []
    return
  }

  if (routeStartNodeId.value === node.id) {
    ui.warn('Выберите вторую точку маршрута')
    return
  }

  routeEndNodeId.value = node.id
  await buildRoutePath()
}

async function buildRoutePath() {
  if (!selectedFloorId.value || !routeStartNodeId.value || !routeEndNodeId.value) return

  try {
    const response = await routeGraphApi.buildPath(selectedFloorId.value, {
      start_node_id: routeStartNodeId.value,
      end_node_id: routeEndNodeId.value,
    })
    routePathNodes.value = response.data.nodes || []
  } catch (error) {
    routePathNodes.value = []
    if (error?.response?.status === 404) {
      ui.warn('Маршрут между выбранными точками не найден')
    } else {
      ui.error(ui.getErrorMessage(error, 'Не удалось построить маршрут'))
    }
  }
}

function onPlanImageError(event) {
  event.target.style.display = 'none'
}

async function loadInitialData() {
  try {
    const [response] = await Promise.all([
      buildingsApi.getBuildings(),
      loadGuests(),
    ])
    buildings.value = response.data

    if (!selectedBuildingId.value && buildings.value.length > 0) {
      selectedBuildingId.value = String(buildings.value[0].id)
    } else if (selectedBuildingId.value) {
      await loadFloorsForBuilding(selectedBuildingId.value)
    }
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось загрузить данные страницы плана здания'))
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
    activeCameraId.value = null
    clearRouteGraphState()
    clearCameraZonesState()
    clearGuestRoute()
    return
  }

  try {
    const [floorRes, camerasRes] = await Promise.all([
      floorsApi.getFloor(selectedFloorId.value),
      camerasApi.getCameras({ buildingId: selectedBuildingId.value, floorId: selectedFloorId.value }),
    ])
    const floor = floorRes.data
    floors.value = floors.value.map((item) => (item.id === floor.id ? floor : item))
    mappedCameras.value = camerasRes.data.map((camera, index) => ({
      ...camera,
      plan_x: typeof camera.plan_x === 'number' && camera.plan_x !== null ? camera.plan_x : distributeFallbackX(index, camerasRes.data.length),
      plan_y: typeof camera.plan_y === 'number' && camera.plan_y !== null ? camera.plan_y : 0.5,
    }))
    if (!mappedCameras.value.some((item) => item.id === activeCameraId.value)) {
      activeCameraId.value = null
    }
    planVersion.value = Date.now()
    await Promise.all([loadRouteGraph(), loadCameraZones()])
    clearGuestRoute()
    await nextTick()
    updatePlanImageMetrics()
  } catch (error) {
    mappedCameras.value = []
    activeCameraId.value = null
    clearRouteGraphState()
    clearCameraZonesState()
    clearGuestRoute()
    ui.error(ui.getErrorMessage(error, 'Не удалось загрузить данные этажа'))
  }
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
      address: buildingForm.value.address.trim() || null,
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
      remove_plan: false,
    }
  } else {
    floorForm.value = {
      id: null,
      building_id: String(selectedBuildingId.value),
      name: '',
      floor_number: '',
      planFile: null,
      remove_plan: false,
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
  clearRouteGraphState()
  clearCameraZonesState()
  clearGuestRoute()
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
    clearRouteGraphState()
    clearCameraZonesState()
    clearGuestRoute()
    return
  }
  await loadFloorContext()
})

onMounted(async () => {
  await loadInitialData()
  window.addEventListener('resize', updatePlanImageMetrics)
  if (window.ResizeObserver && mapContainer.value) {
    planResizeObserver = new ResizeObserver(updatePlanImageMetrics)
    planResizeObserver.observe(mapContainer.value)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updatePlanImageMetrics)
  if (planResizeObserver) {
    planResizeObserver.disconnect()
    planResizeObserver = null
  }
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
.filters-row { display: grid; grid-template-columns: minmax(190px, 1fr) minmax(190px, 1fr) auto; gap: 1rem; padding: 1rem 1.25rem; align-items: end; }
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

.tracking-grid { display: flex; flex-direction: row; gap: 1rem; height: fit-content; max-height: 800px; align-items: stretch; }
.map-section { flex: 2.1; display: flex; flex-direction: column; padding: 1rem; min-height: 0; }
.logs-section, .editor-sidebar { flex: 1; display: flex; flex-direction: column; padding: 1rem; min-height: 0; }
.map-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; gap: 1rem; }
.map-header h2, .logs-section h2, .editor-sidebar h2 { margin: 0; font-size: 1.15rem; color: #0f172a; }
.map-header p { margin: 0.25rem 0 0; color: #64748b; font-size: 0.88rem; }

.plan-status { padding: 0.35rem 0.7rem; border-radius: 999px; font-size: 0.75rem; font-weight: 700; }
.plan-status.ready { background: #dcfce7; color: #166534; }
.plan-status.missing { background: #fef3c7; color: #92400e; }

.route-toolbar { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.75rem; padding: 0.65rem; border-radius: 10px; background: #f8fafc; border: 1px solid #e2e8f0; }
.mode-button { border: 1px solid #cbd5e1; border-radius: 999px; background: #ffffff; color: #334155; padding: 0.45rem 0.75rem; font-weight: 700; cursor: pointer; }
.mode-button.active { border-color: #0891b2; background: #cffafe; color: #155e75; }
.mode-button:disabled { opacity: 0.55; cursor: not-allowed; }
.btn-compact { padding: 0.45rem 0.65rem; }
.graph-counter { margin-left: auto; color: #475569; font-size: 0.85rem; font-weight: 700; }

.map-container { position: relative; flex: 1; min-height: 520px; background: #f8fafc; border-radius: 10px; overflow: hidden; border: 1px solid #e2e8f0; }
.map-container.is-editing { cursor: move; }
.building-plan { width: 100%; height: 100%; object-fit: contain; pointer-events: none; }
.plan-empty-state { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.75rem; color: #94a3b8; text-align: center; padding: 2rem; }
.plan-empty-state i { font-size: 2rem; }
.plan-empty-title { color: #475569; font-weight: 700; }
.plan-empty-text { max-width: 360px; line-height: 1.4; }

.route-graph-layer { position: absolute; z-index: 1; overflow: visible; touch-action: none; }
.route-graph-layer.is-markup-mode { cursor: crosshair; }
.route-graph-layer.is-path-mode { cursor: default; }
.route-graph-layer.is-zone-mode { cursor: crosshair; }
.camera-zone-polygon { fill: rgba(14, 165, 233, 0.16); stroke: rgba(2, 132, 199, 0.78); stroke-width: 3; cursor: pointer; }
.camera-zone-polygon.selected { fill: rgba(16, 185, 129, 0.24); stroke: #059669; stroke-width: 4; }
.camera-zone-polygon.draft { fill: rgba(245, 158, 11, 0.18); stroke: #f59e0b; stroke-dasharray: 8 6; }
.camera-zone-polygon.guest-route-zone { fill: rgba(251, 113, 133, 0.22); stroke: #f43f5e; }
.camera-zone-point { fill: #ffffff; stroke: #f97316; stroke-width: 4; cursor: grab; filter: drop-shadow(0 2px 4px rgba(15, 23, 42, 0.24)); }
.camera-zone-point:active { cursor: grabbing; }
.route-edge-line { stroke: #111827; stroke-width: 2.5; stroke-linecap: round; cursor: pointer; opacity: 0.82; }
.route-edge-line:hover, .route-edge-line.selected { stroke: #f97316; stroke-width: 4; opacity: 1; }
.route-edge-draft { stroke: #0891b2; stroke-width: 3; stroke-dasharray: 10 8; stroke-linecap: round; pointer-events: none; }
.route-path-line { stroke: #ef4444; stroke-width: 8; stroke-linecap: round; stroke-linejoin: round; pointer-events: none; filter: drop-shadow(0 2px 4px rgba(239, 68, 68, 0.35)); }
.guest-probable-route-line { stroke: #7c3aed; stroke-width: 10; stroke-linecap: round; stroke-linejoin: round; pointer-events: none; filter: drop-shadow(0 3px 6px rgba(124, 58, 237, 0.36)); }
.guest-route-direction-arrow { fill: #7c3aed; }
.guest-route-event-marker circle { fill: #111827; stroke: #ffffff; stroke-width: 4; filter: drop-shadow(0 3px 5px rgba(15, 23, 42, 0.3)); }
.guest-route-event-marker text { fill: #ffffff; font-size: 16px; font-weight: 800; pointer-events: none; }
.route-node { fill: #ffffff; stroke: #0891b2; stroke-width: 4; cursor: pointer; filter: drop-shadow(0 2px 4px rgba(15, 23, 42, 0.25)); }
.route-node:hover { fill: #cffafe; stroke: #0e7490; }
.route-start-node { fill: #dcfce7; stroke: #16a34a; }
.route-end-node { fill: #fee2e2; stroke: #dc2626; }

.camera-pin { position: absolute; width: 30px; height: 30px; border-radius: 50%; background: #3b82f6; color: #ffffff; display: flex; align-items: center; justify-content: center; transform: translate(-50%, -50%); box-shadow: 0 4px 10px rgba(15, 23, 42, 0.2); cursor: pointer; z-index: 2; }
.is-editing .camera-pin { cursor: grab; }
.is-editing .camera-pin:active { cursor: grabbing; }
.camera-pin.active-pin { background: #10b981; box-shadow: 0 0 0 5px rgba(16, 185, 129, 0.18); }
.camera-tooltip { display: none; position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%); background: #0f172a; color: white; padding: 0.35rem 0.55rem; border-radius: 6px; font-size: 0.75rem; white-space: nowrap; }
.camera-pin:hover .camera-tooltip { display: block; }
.camera-zone-indicator { position: absolute; right: -2px; top: -2px; width: 10px; height: 10px; border-radius: 999px; background: #f97316; border: 2px solid #ffffff; }
.pulse-ring { position: absolute; inset: -2px; border: 2px solid #10b981; border-radius: 50%; animation: pulse 1.5s infinite; }
@keyframes pulse { 0% { transform: scale(1); opacity: 1; } 100% { transform: scale(2.4); opacity: 0; } }

.section-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.section-header p { margin: 0.25rem 0 0; color: #64748b; font-size: 0.85rem; }
.item-count { min-width: 34px; height: 28px; padding: 0 0.6rem; border-radius: 999px; background: #dbeafe; color: #1d4ed8; display: inline-flex; align-items: center; justify-content: center; font-weight: 800; }
.logs-list { margin-top: 1rem; overflow-y: auto; display: flex; flex-direction: column; gap: 0.75rem; flex: 1; height: 0; padding-right: 0.5rem; }
.camera-card { display: flex; gap: 0.8rem; align-items: center; padding: 0.8rem 0.9rem; border-radius: 8px; background: #f8fafc; border: 1px solid #e2e8f0; cursor: pointer; }
.camera-card:hover { border-color: #bfdbfe; background: #eff6ff; }
.camera-card.selected { border-color: #10b981; background: #ecfdf5; }
.camera-card-icon { width: 34px; height: 34px; border-radius: 999px; background: #dbeafe; color: #2563eb; display: flex; align-items: center; justify-content: center; }
.camera-card-name { color: #0f172a; font-weight: 700; }
.camera-card-meta { margin-top: 0.2rem; color: #64748b; font-size: 0.82rem; }
.camera-card-meta.zone-ready { color: #059669; font-weight: 700; }
.empty-logs, .empty-selection { margin: auto 0; text-align: center; color: #94a3b8; }

.side-panel { margin-top: 1rem; border-top: 1px solid #e2e8f0; padding-top: 1rem; }
.side-panel h3 { margin: 0 0 0.65rem; color: #0f172a; font-size: 1rem; }
.zone-editor-box { border: 1px solid #e2e8f0; border-radius: 10px; background: #f8fafc; padding: 0.85rem; }
.zone-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.75rem; }
.compact-form { margin-bottom: 0.65rem; }
.camera-zone-warning { margin-top: 0.75rem; border: 1px solid #fde68a; border-radius: 8px; background: #fffbeb; color: #92400e; padding: 0.65rem; font-size: 0.82rem; line-height: 1.35; }
.guest-route-events { display: flex; flex-direction: column; gap: 0.55rem; margin-top: 0.75rem; }
.guest-route-event-row { display: flex; align-items: center; gap: 0.65rem; padding: 0.6rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; }
.event-order { width: 26px; height: 26px; border-radius: 999px; background: #7c3aed; color: #ffffff; display: inline-flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.8rem; }

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
.upload-hint { margin: 0; color: #64748b; font-size: 0.8rem; }
.modal-actions { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 0.75rem; }

@media (max-width: 1200px) {
  .filters-row { grid-template-columns: 1fr 1fr; }
  .tracking-grid { flex-direction: column; max-height: none; }
  .map-container { min-height: 420px; }
}
@media (max-width: 768px) {
  .header-panel { flex-direction: column; gap: 1rem; }
  .filters-row, .form-grid { grid-template-columns: 1fr; }
}
</style>
