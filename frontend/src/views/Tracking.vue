<template>
  <div class="page-container">
    <TrackingPageHeader
      :can-edit-plan="canEditPlan"
      :selected-building-id="selectedBuildingId"
      :selected-floor-id="selectedFloorId"
      @open-building="openBuildingModal"
      @open-floor="openFloorModal"
      @open-floor-plan="openFloorModal(true)"
    />

    <TrackingFloorControls
      v-model:selected-building-id="selectedBuildingId"
      v-model:selected-floor-id="selectedFloorId"
      :buildings="buildings"
      :floors="floors"
      :floors-loading="floorsLoading"
      :can-edit-plan="canEditPlan"
      :is-edit-mode="isEditMode"
      :saving-plan="savingPlan"
      @toggle-edit="toggleEditMode"
      @cancel-edit="cancelEditMode"
      @save-plan="savePlan"
    />

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

        <RouteGraphToolbar
          :can-edit-plan="canEditPlan"
          :graph-mode="graphMode"
          :route-graph-available="routeGraphAvailable"
          :is-edit-mode="isEditMode"
          :route-graph-loading="routeGraphLoading"
          :node-count="routeNodes.length"
          :edge-count="routeEdges.length"
          :route-path-count="routePathNodes.length"
          @set-graph-mode="setGraphMode"
          @clear-route-path="clearRoutePath"
          @clear-route-graph="confirmClearRouteGraph"
        />

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
            <polygon
              v-for="zone in renderedCameraZones"
              :key="`zone-${zone.camera_id}`"
              :class="['camera-zone-polygon', { selected: zone.selected }]"
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

      <FloorCamerasPanel
        v-if="!isEditMode"
        :mapped-cameras="mappedCameras"
        :active-camera-id="activeCameraId"
        :camera-zones-by-camera-id="cameraZonesByCameraId"
        :selected-floor-label="selectedFloorLabel"
        @camera-click="onCameraCardClick"
      />

      <PlanEditorSidebar
        v-else
        :unassigned-cameras="unassignedCameras"
        :active-camera="activeCamera"
        :selected-camera-has-zone="selectedCameraHasZone"
        :zone-draft-camera-id="zoneDraftCameraId"
        :zone-draft-points="zoneDraftPoints"
        :zone-saving="zoneSaving"
        :editable-zone-points="editableZonePoints"
        @add-camera="addCameraToFloor"
        @remove-camera="removeCameraFromFloor"
        @start-zone-draft="startZoneDraft"
        @save-zone="saveActiveCameraZone"
        @reset-zone="resetActiveZoneDraft"
        @delete-zone="deleteActiveCameraZone"
      />
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
import FloorCamerasPanel from '../components/tracking/FloorCamerasPanel.vue'
import PlanEditorSidebar from '../components/tracking/PlanEditorSidebar.vue'
import RouteGraphToolbar from '../components/tracking/RouteGraphToolbar.vue'
import TrackingFloorControls from '../components/tracking/TrackingFloorControls.vue'
import TrackingPageHeader from '../components/tracking/TrackingPageHeader.vue'
import { buildingsApi } from '../api/buildings'
import { buildWsUrl } from '../api/client'
import { cameraVisibilityApi } from '../api/cameraVisibility'
import { camerasApi } from '../api/cameras'
import { floorsApi } from '../api/floors'
import { routeGraphApi } from '../api/routeGraph'
import { formatPolygonPoints } from '../services/geometry'
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
      selected: zone.camera_id === activeCameraId.value,
    }))
)
const selectedCameraHasZone = computed(() => Boolean(activeCameraZone.value))

function clamp01(value) {
  return Math.max(0, Math.min(1, value))
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
  cameraZones.value = cameraZones.value.filter((zone) => zone.camera_id !== camera.id)
  if (zoneDraftCameraId.value === camera.id) {
    zoneDraftPoints.value = []
    zoneDraftCameraId.value = null
    draggingZonePointIndex.value = null
    draggingZonePolygon.value = null
  }
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
  const hasZoneDraft = Boolean(zoneDraftCameraId.value && zoneDraftPoints.value.length)
  if (hasZoneDraft && zoneDraftPoints.value.length !== 4) {
    ui.warn('Зона видимости начата, но не завершена: поставьте 4 точки или нажмите «Сбросить».')
    return
  }

  const zoneDraftToSave =
    hasZoneDraft && !camerasToRemoveFromFloor.value.includes(zoneDraftCameraId.value)
      ? {
          cameraId: zoneDraftCameraId.value,
          points: zoneDraftPoints.value.map((point) => ({ ...point })),
        }
      : null

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

    if (zoneDraftToSave) {
      await persistCameraZone(zoneDraftToSave.cameraId, zoneDraftToSave.points, { showSuccess: false })
    }

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

    ui.success(zoneDraftToSave ? 'Положение камер и зона видимости сохранены' : 'Положение камер успешно сохранено')
  } catch (error) {
    console.error('Ошибка сохранения плана:', error.response?.data || error)
    ui.error(ui.getErrorMessage(error, 'Не удалось сохранить план камер или зону видимости'))
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
    const mappedCameraIds = new Set(mappedCameras.value.map((camera) => camera.id))
    cameraZones.value = (response.data.zones || []).filter((zone) => mappedCameraIds.has(zone.camera_id))
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

async function persistCameraZone(cameraId, points, { showSuccess = true } = {}) {
  const response = await cameraVisibilityApi.saveCameraZone(cameraId, {
    floor_id: Number(selectedFloorId.value),
    points,
  })
  const nextZone = response.data
  const existingIndex = cameraZones.value.findIndex((zone) => zone.camera_id === nextZone.camera_id)
  if (existingIndex >= 0) {
    cameraZones.value[existingIndex] = nextZone
  } else {
    cameraZones.value.push(nextZone)
  }

  if (zoneDraftCameraId.value === cameraId) {
    zoneDraftPoints.value = []
    zoneDraftCameraId.value = null
    draggingZonePointIndex.value = null
    draggingZonePolygon.value = null
  }

  if (showSuccess) ui.success('Зона видимости камеры сохранена')
  return nextZone
}

async function saveActiveCameraZone() {
  if (!activeCamera.value || !selectedFloorId.value) return
  if (editableZonePoints.value.length !== 4) return ui.warn('Зона видимости должна содержать ровно 4 точки')

  zoneSaving.value = true
  try {
    await persistCameraZone(activeCamera.value.id, editableZonePoints.value)
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
    ui.success('Зона видимости камеры удалена')
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось удалить зону видимости камеры'))
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
    const response = await buildingsApi.getBuildings()
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
    await nextTick()
    updatePlanImageMetrics()
  } catch (error) {
    mappedCameras.value = []
    activeCameraId.value = null
    clearRouteGraphState()
    clearCameraZonesState()
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
.map-section { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04); }
.form-input { width: 100%; padding: 0.7rem 0.9rem; border-radius: 8px; border: 1px solid #cbd5e1; background: #f8fafc; font-size: 0.95rem; color: #1e293b; }
.form-input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12); background: #ffffff; }

.btn-primary, .btn-secondary, .btn-success, .btn-text { border: none; border-radius: 8px; padding: 0.65rem 1rem; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 0.5rem; }
.btn-primary { background: #3b82f6; color: #ffffff; }
.btn-secondary { background: #eef2ff; color: #334155; }
.btn-success { background: #10b981; color: #ffffff; }
.btn-text { background: transparent; color: #64748b; }
.btn-primary:disabled, .btn-secondary:disabled, .btn-success:disabled, .btn-text:disabled { opacity: 0.6; cursor: not-allowed; }

.tracking-grid { display: flex; flex-direction: row; gap: 1rem; height: fit-content; max-height: 800px; align-items: stretch; }
.map-section { flex: 2.35; display: flex; flex-direction: column; padding: 1rem; min-height: 0; }
.map-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; gap: 1rem; }
.map-header h2 { margin: 0; font-size: 1.15rem; color: #0f172a; }
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

.route-graph-layer { position: absolute; z-index: 1; overflow: visible; touch-action: none; }
.route-graph-layer.is-markup-mode { cursor: crosshair; }
.route-graph-layer.is-path-mode { cursor: default; }
.route-graph-layer.is-zone-mode { cursor: crosshair; }
.camera-zone-polygon { fill: rgba(14, 165, 233, 0.16); stroke: rgba(2, 132, 199, 0.78); stroke-width: 3; cursor: pointer; }
.camera-zone-polygon.selected { fill: rgba(16, 185, 129, 0.24); stroke: #059669; stroke-width: 4; }
.camera-zone-polygon.draft { fill: rgba(245, 158, 11, 0.18); stroke: #f59e0b; stroke-dasharray: 8 6; }
.camera-zone-point { fill: #ffffff; stroke: #f97316; stroke-width: 4; cursor: grab; filter: drop-shadow(0 2px 4px rgba(15, 23, 42, 0.24)); }
.camera-zone-point:active { cursor: grabbing; }
.route-edge-line { stroke: #111827; stroke-width: 2.5; stroke-linecap: round; cursor: pointer; opacity: 0.82; }
.route-edge-line:hover, .route-edge-line.selected { stroke: #f97316; stroke-width: 4; opacity: 1; }
.route-edge-draft { stroke: #0891b2; stroke-width: 3; stroke-dasharray: 10 8; stroke-linecap: round; pointer-events: none; }
.route-path-line { stroke: #ef4444; stroke-width: 8; stroke-linecap: round; stroke-linejoin: round; pointer-events: none; filter: drop-shadow(0 2px 4px rgba(239, 68, 68, 0.35)); }
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

.btn-danger { color: #ef4444; }
.btn-danger:hover { color: #dc2626; background: #fee2e2; }

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
  .tracking-grid { flex-direction: column; max-height: none; }
  .map-container { min-height: 420px; }
}
@media (max-width: 768px) {
  .form-grid { grid-template-columns: 1fr; }
}
</style>
