<template>
  <div class="page-container">
    <div class="header-actions">
      <div>
        <h1 class="page-title">Гостевые пропуска</h1>
        <p class="page-subtitle">Выдача временных пропусков и фото-фиксация посетителей с камер проходной.</p>
      </div>
      <button v-if="canManageGuests" class="btn-primary" @click="openNewDialog">
        <i class="pi pi-plus"></i> Выдать пропуск
      </button>
    </div>

    <div class="filters-bar">
      <div class="search-box">
        <i class="pi pi-search"></i>
        <input type="text" v-model="searchQuery" placeholder="Поиск по ФИО гостя или сотрудника..." />
      </div>

      <select v-model="selectedStatus" class="filter-select">
        <option value="all">Все статусы</option>
        <option value="active">Только активные</option>
        <option value="expired">Истекшие / закрытые</option>
      </select>

      <select v-model="sortBy" class="filter-select">
        <option value="newest">Сначала новые</option>
        <option value="oldest">Сначала старые</option>
        <option value="name">По алфавиту (ФИО)</option>
      </select>
    </div>

    <div class="cards-grid">
      <div v-for="guest in filteredGuests" :key="guest.id" class="employee-card">
        <div class="card-header">
          <div class="status-badge" :class="isPassValid(guest.valid_until, guest.is_active) ? 'active' : 'blocked'">
            {{ isPassValid(guest.valid_until, guest.is_active) ? 'ПРОПУСК АКТИВЕН' : 'ИСТЕК / ЗАКРЫТ' }}
          </div>
          <div class="card-actions">
            <button
              v-if="guest.has_body_embedding"
              class="btn-icon"
              @click="openRouteDialog(guest)"
              title="Построить маршрут гостя"
            >
              <i class="pi pi-map-marker"></i>
            </button>
            <button
              v-else-if="canManageGuests && isPassValid(guest.valid_until, guest.is_active)"
              class="btn-icon"
              @click="openBodyPhotoDialog(guest)"
              title="Добавить фото полного роста для Re-ID"
            >
              <i class="pi pi-id-card"></i>
            </button>
            <button
              v-if="canManageGuests && isPassValid(guest.valid_until, guest.is_active)"
              class="btn-icon warning"
              @click="deactivateGuest(guest.id)"
              title="Аннулировать пропуск"
            >
              <i class="pi pi-ban"></i>
            </button>
          </div>
        </div>

        <div class="card-body">
          <div class="avatar-container">
            <img v-if="guest.photo_id" :src="guestsApi.getGuestPhotoUrl(guest.photo_id)" alt="Фото гостя" class="avatar-img" />
            <div v-else class="avatar-placeholder">
              <i class="pi" :class="guest.has_body_embedding ? 'pi-id-card' : 'pi-user'"></i>
            </div>
          </div>

          <h3 class="emp-name">{{ guest.last_name }} {{ guest.first_name }}</h3>
          <p class="emp-middle-name">{{ guest.middle_name || ' ' }}</p>

          <div class="guest-info">
            <div class="info-row">
              <i class="pi pi-user"></i>
              <span>{{ guest.employee_name || 'Сотрудник не указан' }}</span>
            </div>
            <div class="info-row" :class="{ expired: !isPassValid(guest.valid_until, guest.is_active) }">
              <i class="pi pi-clock"></i>
              <span>До: {{ formatDate(guest.valid_until) }}</span>
            </div>
            <div v-if="guest.has_body_embedding" class="info-row reid-row">
              <i class="pi pi-eye"></i>
              <span>Re-ID по силуэту активен</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="filteredGuests.length === 0" class="empty-state">
        <i class="pi pi-id-card empty-icon"></i>
        <h3>Нет подходящих пропусков</h3>
        <p>По вашему запросу ничего не найдено или список пуст.</p>
      </div>
    </div>

    <div v-if="displayDialog" class="modal-overlay" @click.self="closeDialog">
      <div class="modal-content wide-modal">
        <div class="modal-header">
          <h2>Оформление гостевого пропуска</h2>
          <button class="btn-icon close-btn" @click="closeDialog">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="modal-body-split">
          <div class="photo-column">
            <div class="photo-upload-block">
              <label class="photo-block-title">Фото лица</label>
              <div class="avatar-preview">
                <img v-if="facePhotoPreview" :src="facePhotoPreview" class="avatar-img large" />
                <div v-else class="avatar-placeholder large">
                  <i class="pi pi-camera"></i>
                </div>
              </div>

              <div class="capture-controls">
                <label class="control-label">Камера проходной:</label>
                <select v-model="selectedCameraId" class="form-input">
                  <option value="" disabled>Выберите камеру...</option>
                  <option v-for="cam in activeCameras" :key="cam.id" :value="cam.id">
                    {{ cam.name }}
                  </option>
                </select>

                <button class="btn-primary full-width-btn" @click="takeSnapshot" :disabled="!selectedCameraId || isTakingSnapshot">
                  <i class="pi" :class="isTakingSnapshot ? 'pi-spin pi-spinner' : 'pi-camera'"></i>
                  Сделать снимок лица
                </button>

                <div class="divider"><span>ИЛИ</span></div>

                <button class="btn-text upload-btn full-width-btn" @click="$refs.faceFileInput.click()">
                  <i class="pi pi-upload"></i> Загрузить фото лица
                </button>
                <input type="file" accept="image/*" ref="faceFileInput" class="hidden-input" @change="onFaceFileSelected" />
              </div>
            </div>

            <div class="photo-upload-block">
              <label class="photo-block-title">Фото полного роста для Re-ID</label>
              <div class="avatar-preview body-preview">
                <img v-if="bodyPhotoPreview" :src="bodyPhotoPreview" class="avatar-img large" />
                <div v-else class="avatar-placeholder large">
                  <i class="pi pi-id-card"></i>
                </div>
              </div>

              <button class="btn-text upload-btn full-width-btn" @click="$refs.bodyFileInput.click()">
                <i class="pi pi-upload"></i> Загрузить полный рост
              </button>
              <input type="file" accept="image/*" ref="bodyFileInput" class="hidden-input" @change="onBodyFileSelected" />
              <p class="capture-hint">Это фото нужно, чтобы Re-ID отслеживал гостя по одежде и силуэту.</p>
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
                <label>К кому пришли <span class="required">*</span></label>
                <div class="employee-select">
                  <button type="button" class="form-input employee-select-trigger" @click="toggleEmployeeDropdown">
                    <span :class="{ 'placeholder-text': !selectedEmployeeName }">
                      {{ selectedEmployeeName || 'Выберите сотрудника...' }}
                    </span>
                    <i class="pi" :class="employeeDropdownOpen ? 'pi-chevron-up' : 'pi-chevron-down'"></i>
                  </button>

                  <div v-if="employeeDropdownOpen" class="employee-select-panel">
                    <div class="employee-search-box">
                      <i class="pi pi-search"></i>
                      <input
                        v-model="employeeSearchQuery"
                        type="text"
                        class="employee-search-input"
                        placeholder="Поиск по ФИО..."
                      />
                    </div>

                    <div class="employee-options-list">
                      <button
                        v-for="employee in filteredEmployeeOptions"
                        :key="employee.id"
                        type="button"
                        class="employee-option"
                        :class="{ selected: String(guestForm.employee_id) === String(employee.id) }"
                        @click="selectEmployee(employee)"
                      >
                        {{ getEmployeeFullName(employee) }}
                      </button>

                      <div v-if="filteredEmployeeOptions.length === 0" class="employee-option-empty">
                        Сотрудники не найдены
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-text" @click="closeDialog">Отмена</button>
          <button class="btn-primary" @click="saveGuest">Выдать пропуск</button>
        </div>
      </div>
    </div>

    <div v-if="bodyPhotoDialogVisible" class="modal-overlay" @click.self="closeBodyPhotoDialog">
      <div class="modal-content small-modal">
        <div class="modal-header">
          <h2>Фото полного роста для Re-ID</h2>
          <button class="btn-icon close-btn" @click="closeBodyPhotoDialog">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <p class="capture-hint">
          Гость: {{ formatGuestName(bodyPhotoGuest) }}. Загрузите кадр, где человек виден в полный рост.
        </p>
        <div class="avatar-preview body-preview modal-preview">
          <img v-if="bodyEnrollmentPreview" :src="bodyEnrollmentPreview" class="avatar-img large" />
          <div v-else class="avatar-placeholder large">
            <i class="pi pi-id-card"></i>
          </div>
        </div>
        <button class="btn-text upload-btn full-width-btn" @click="$refs.bodyEnrollmentInput.click()">
          <i class="pi pi-upload"></i> Выбрать фото полного роста
        </button>
        <input type="file" accept="image/*" ref="bodyEnrollmentInput" class="hidden-input" @change="onBodyEnrollmentFileSelected" />

        <div class="modal-actions">
          <button class="btn-text" @click="closeBodyPhotoDialog">Отмена</button>
          <button class="btn-primary" :disabled="!bodyEnrollmentFile || bodyPhotoSaving" @click="saveGuestBodyPhoto">
            {{ bodyPhotoSaving ? 'Сохранение...' : 'Сохранить Re-ID фото' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="routeDialogVisible" class="modal-overlay" @click.self="closeRouteDialog">
      <div class="modal-content route-modal">
        <div class="modal-header">
          <h2>Маршрут гостя</h2>
          <button class="btn-icon close-btn" @click="closeRouteDialog">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <p class="capture-hint">
          Гость: {{ formatGuestName(routeGuest) }}. Можно мгновенно построить маршрут по уже записанному журналу
          или сначала проанализировать file-видео камер выбранного этажа.
        </p>

        <div class="route-dialog-layout">
          <div class="route-controls-column">
            <div class="form-group">
              <label>Этаж <span class="required">*</span></label>
              <select v-model="routeFloorId" class="form-input" :disabled="routeJobLoading" @change="onRouteFloorChange">
                <option value="" disabled>Выберите этаж...</option>
                <option v-for="floor in floorOptions" :key="floor.id" :value="String(floor.id)">
                  {{ floor.label }}
                </option>
              </select>
            </div>

            <div class="route-time-grid">
              <div class="form-group">
                <label>Дата/время от</label>
                <input v-model="routeTimeFrom" class="form-input" type="datetime-local" :disabled="routeJobLoading" />
              </div>
              <div class="form-group">
                <label>Дата/время до</label>
                <input v-model="routeTimeTo" class="form-input" type="datetime-local" :disabled="routeJobLoading" />
              </div>
            </div>

            <div v-if="routeJob" class="route-job-status">
              <div><b>Статус:</b> {{ formatRouteJobStatus(routeJob.status) }}</div>
              <div><b>Обработано камер:</b> {{ routeJob.processed_cameras }} из {{ routeJob.total_cameras ?? '—' }}</div>
              <div><b>Событий найдено:</b> {{ routeJob.events_written }}</div>
              <div v-if="routeJob.status === 'processing' && routeJob.processed_cameras === 0" class="job-note">
                Первая камера ещё обрабатывается. Счётчик увеличится после завершения анализа этой камеры.
              </div>
              <div v-if="routeJob.error_message" class="job-error">{{ routeJob.error_message }}</div>
              <div v-if="routeJobWarnings.length" class="job-warnings">
                <div v-for="warning in routeJobWarnings" :key="warning">{{ warning }}</div>
              </div>
            </div>

            <div v-if="routeWarnings.length" class="job-warnings route-result-warnings">
              <div v-for="warning in routeWarnings" :key="warning">{{ warning }}</div>
            </div>

            <div class="route-events-panel">
              <div class="route-events-title">
                <span>События маршрута</span>
                <strong>{{ routeEvents.length }}</strong>
              </div>
              <div v-if="routeEvents.length" class="route-events-list">
                <div
                  v-for="(event, index) in routeEvents"
                  :key="`${event.source}-${event.tracking_log_id || event.access_log_id || index}`"
                  class="route-event-row"
                >
                  <span class="route-event-order">{{ index + 1 }}</span>
                  <div>
                    <div class="route-event-camera">{{ event.camera_name || `Камера ${event.camera_id}` }}</div>
                    <div class="route-event-time">{{ formatTimestamp(event.timestamp) }}</div>
                  </div>
                </div>
              </div>
              <div v-else class="route-empty-message">
                После построения здесь появятся камеры в порядке обнаружения гостя.
              </div>
            </div>
          </div>

          <div class="route-map-column">
            <div class="route-map-header">
              <div>
                <strong>Вероятный маршрут</strong>
                <span>Зоны камер и путь по размеченному графу</span>
              </div>
              <span v-if="routeResultLoading" class="route-map-status">Построение...</span>
            </div>

            <div class="route-plan-preview">
              <img
                v-if="routePlanUrl"
                ref="routePlanImage"
                :src="routePlanUrl"
                alt="План этажа"
                class="route-plan-image"
                draggable="false"
                @load="onRoutePlanImageLoad"
              />
              <svg
                v-if="routePlanUrl"
                class="route-plan-overlay"
                :viewBox="routePlanViewBox"
                preserveAspectRatio="xMidYMid meet"
              >
                <defs>
                  <marker
                    id="guest-route-modal-arrow"
                    viewBox="0 0 10 10"
                    refX="8"
                    refY="5"
                    markerWidth="12"
                    markerHeight="12"
                    markerUnits="userSpaceOnUse"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 0 L 10 5 L 0 10 z" class="route-direction-arrow"></path>
                  </marker>
                </defs>

                <polygon
                  v-for="zone in routeCameraZones"
                  :key="`route-zone-${zone.camera_id}`"
                  class="route-camera-zone"
                  :points="formatPolygonPoints(zone.points)"
                />

                <polyline
                  v-if="routePolyline"
                  class="route-result-line"
                  :points="routePolyline"
                  fill="none"
                  vector-effect="non-scaling-stroke"
                  marker-mid="url(#guest-route-modal-arrow)"
                  marker-end="url(#guest-route-modal-arrow)"
                />

                <g
                  v-for="marker in routeEventMarkers"
                  :key="marker.id"
                  class="route-event-marker"
                >
                  <circle :cx="marker.x" :cy="marker.y" :r="routeMarkerRadius" vector-effect="non-scaling-stroke" />
                  <text :x="marker.x" :y="marker.y" text-anchor="middle" dominant-baseline="central">
                    {{ marker.order }}
                  </text>
                </g>
              </svg>
              <div v-if="!routePlanUrl" class="route-plan-empty">
                Для выбранного этажа не загружен план.
              </div>
              <div v-else-if="!routeResult && !routeResultLoading" class="route-plan-empty overlay-empty">
                Нажмите «Построить по журналу» или «Проанализировать видео и построить».
              </div>
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-text" @click="closeRouteDialog">Отмена</button>
          <button class="btn-text route-journal-btn" :disabled="!routeFloorId || routeJobLoading || routeResultLoading" @click="buildRouteFromJournal">
            Построить по журналу
          </button>
          <button class="btn-primary" :disabled="!routeFloorId || routeJobLoading || routeResultLoading" @click="startGuestRouteAnalysis">
            {{ routeJobLoading ? 'Анализ...' : 'Проанализировать видео и построить' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount, onMounted, computed } from 'vue'
import { buildingsApi } from '../api/buildings'
import { guestsApi } from '../api/guests'
import { camerasApi } from '../api/cameras'
import { employeesApi } from '../api/employees'
import { floorsApi } from '../api/floors'
import { guestRoutesApi } from '../api/guestRoutes'
import { formatPolygonPoints, polygonCentroid } from '../services/geometry'
import { useAuth } from '../services/auth'
import { useUi } from '../services/ui'

defineOptions({ name: 'GuestsPage' })

const auth = useAuth()
const ui = useUi()
const canManageGuests = computed(() => auth.hasAnyRole('super_admin', 'checkpoint_operator'))

const guests = ref([])
const cameras = ref([])
const employees = ref([])
const buildings = ref([])
const floors = ref([])

const searchQuery = ref('')
const selectedStatus = ref('active')
const sortBy = ref('newest')

const displayDialog = ref(false)
const isTakingSnapshot = ref(false)
const selectedCameraId = ref('')
const employeeDropdownOpen = ref(false)
const employeeSearchQuery = ref('')

const faceFileInput = ref(null)
const bodyFileInput = ref(null)
const facePhotoPreview = ref(null)
const bodyPhotoPreview = ref(null)

const bodyPhotoDialogVisible = ref(false)
const bodyPhotoGuest = ref(null)
const bodyEnrollmentInput = ref(null)
const bodyEnrollmentFile = ref(null)
const bodyEnrollmentPreview = ref(null)
const bodyPhotoSaving = ref(false)

const routeDialogVisible = ref(false)
const routeGuest = ref(null)
const routeFloorId = ref('')
const routeJob = ref(null)
const routeJobLoading = ref(false)
const routeResultLoading = ref(false)
const routeResult = ref(null)
const routeTimeFrom = ref('')
const routeTimeTo = ref('')
const routePlanImage = ref(null)
const routePlanVersion = ref(Date.now())
const routePlanMetrics = ref({
  naturalWidth: 1,
  naturalHeight: 1,
})
let routeJobPollTimer = null

const guestForm = ref({
  last_name: '',
  first_name: '',
  middle_name: '',
  employee_id: '',
  valid_until: '',
  facePhotoFile: null,
  bodyPhotoFile: null,
})

const parseLocalDate = (dateString) => {
  const parsed = new Date(dateString)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const loadData = async () => {
  try {
    const [camerasRes, guestsRes, employeesRes, buildingsRes, floorsRes] = await Promise.all([
      camerasApi.getCameras(),
      guestsApi.getGuests(),
      employeesApi.getEmployees(0, 1000),
      buildingsApi.getBuildings(),
      floorsApi.getFloors(),
    ])

    cameras.value = camerasRes.data
    guests.value = guestsRes.data
    employees.value = employeesRes.data.filter(employee => employee.is_active)
    buildings.value = buildingsRes.data
    floors.value = floorsRes.data
  } catch (error) {
    console.error('Ошибка загрузки данных:', error)
  }
}

const activeCameras = computed(() => {
  return cameras.value.filter(camera => camera.is_active)
})

const getEmployeeFullName = (employee) => {
  return [employee.last_name, employee.first_name, employee.middle_name].filter(Boolean).join(' ')
}

const selectedEmployeeName = computed(() => {
  const employee = employees.value.find(item => String(item.id) === String(guestForm.value.employee_id))
  return employee ? getEmployeeFullName(employee) : ''
})

const floorOptions = computed(() => {
  const buildingById = new Map(buildings.value.map(building => [building.id, building]))
  return floors.value.map(floor => {
    const buildingName = buildingById.get(floor.building_id)?.name || `Здание ${floor.building_id}`
    return {
      ...floor,
      label: `${buildingName} · ${floor.name} (${floor.floor_number} этаж)`,
    }
  })
})

const selectedRouteFloor = computed(() =>
  floors.value.find(floor => String(floor.id) === String(routeFloorId.value)) || null
)

const routePlanUrl = computed(() => {
  if (!selectedRouteFloor.value?.has_plan || !routeFloorId.value) return ''
  const baseUrl = floorsApi.getFloorPlanUrl(routeFloorId.value)
  const separator = baseUrl.includes('?') ? '&' : '?'
  return `${baseUrl}${separator}v=${routePlanVersion.value}`
})

const routePlanViewBox = computed(() => {
  const { naturalWidth, naturalHeight } = routePlanMetrics.value
  return `0 0 ${naturalWidth || 1} ${naturalHeight || 1}`
})

const routePolyline = computed(() =>
  (routeResult.value?.route_nodes || []).map(node => `${node.x},${node.y}`).join(' ')
)

const routeCameraZones = computed(() => routeResult.value?.camera_zones || [])
const routeEvents = computed(() => routeResult.value?.events || [])
const routeWarnings = computed(() => routeResult.value?.warnings || [])
const routeJobWarnings = computed(() => {
  const warnings = routeJob.value?.warnings || []
  const routeWarningSet = new Set(routeWarnings.value)
  return warnings.filter(warning => !routeWarningSet.has(warning))
})
const routeMarkerRadius = computed(() => Math.max(9, routePlanMetrics.value.naturalWidth / 115))

const routeEventMarkers = computed(() =>
  routeEvents.value
    .map((event, index) => {
      if (event.route_anchor) {
        return {
          x: event.route_anchor.x,
          y: event.route_anchor.y,
          id: `${event.source}-${event.tracking_log_id || event.access_log_id || index}`,
          order: index + 1,
        }
      }

      const zone = routeCameraZones.value.find(item => item.camera_id === event.camera_id)
      if (!zone?.points?.length) return null
      return {
        ...polygonCentroid(zone.points),
        id: `${event.source}-${event.tracking_log_id || event.access_log_id || index}`,
        order: index + 1,
      }
    })
    .filter(Boolean)
)

const filteredEmployeeOptions = computed(() => {
  const query = employeeSearchQuery.value.trim().toLowerCase()
  if (!query) return employees.value
  return employees.value.filter(employee => getEmployeeFullName(employee).toLowerCase().includes(query))
})

const filteredGuests = computed(() => {
  let result = guests.value.filter(guest => {
    const query = searchQuery.value.toLowerCase()
    const fullName = `${guest.last_name} ${guest.first_name} ${guest.middle_name || ''}`.toLowerCase()
    const employeeName = (guest.employee_name || '').toLowerCase()
    const matchesSearch = fullName.includes(query) || employeeName.includes(query)

    const isValid = isPassValid(guest.valid_until, guest.is_active)

    let matchesStatus = true
    if (selectedStatus.value === 'active') matchesStatus = isValid
    if (selectedStatus.value === 'expired') matchesStatus = !isValid

    return matchesSearch && matchesStatus
  })

  result.sort((a, b) => {
    if (sortBy.value === 'newest') return b.id - a.id
    if (sortBy.value === 'oldest') return a.id - b.id
    if (sortBy.value === 'name') {
      const nameA = `${a.last_name} ${a.first_name}`.toLowerCase()
      const nameB = `${b.last_name} ${b.first_name}`.toLowerCase()
      return nameA.localeCompare(nameB)
    }
    return 0
  })

  return result
})

const isPassValid = (dateString, isActive) => {
  if (isActive === false) return false
  const parsed = parseLocalDate(dateString)
  return parsed ? parsed > new Date() : false
}

const formatDate = (dateString) => {
  const d = parseLocalDate(dateString)
  if (!d) return 'Некорректная дата'
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const toggleEmployeeDropdown = () => {
  employeeDropdownOpen.value = !employeeDropdownOpen.value
  if (!employeeDropdownOpen.value) employeeSearchQuery.value = ''
}

const selectEmployee = (employee) => {
  guestForm.value.employee_id = String(employee.id)
  employeeDropdownOpen.value = false
  employeeSearchQuery.value = ''
}

const formatGuestName = (guest) => {
  if (!guest) return ''
  return [guest.last_name, guest.first_name, guest.middle_name].filter(Boolean).join(' ')
}

const revokePreview = (previewRef) => {
  if (previewRef.value) {
    URL.revokeObjectURL(previewRef.value)
    previewRef.value = null
  }
}

const onFaceFileSelected = (event) => {
  const file = event.target.files[0]
  if (file) {
    guestForm.value.facePhotoFile = file
    revokePreview(facePhotoPreview)
    facePhotoPreview.value = URL.createObjectURL(file)
  }
}

const onBodyFileSelected = (event) => {
  const file = event.target.files[0]
  if (file) {
    guestForm.value.bodyPhotoFile = file
    revokePreview(bodyPhotoPreview)
    bodyPhotoPreview.value = URL.createObjectURL(file)
  }
}

const takeSnapshot = async () => {
  if (!selectedCameraId.value) return
  isTakingSnapshot.value = true
  try {
    const res = await camerasApi.getSnapshot(selectedCameraId.value)
    const blob = res.data
    const file = new File([blob], 'face_snapshot.jpg', { type: 'image/jpeg' })
    guestForm.value.facePhotoFile = file

    revokePreview(facePhotoPreview)
    facePhotoPreview.value = URL.createObjectURL(blob)
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось сделать снимок. Камера недоступна или в кадре нет людей.'))
  } finally {
    isTakingSnapshot.value = false
  }
}

const openNewDialog = () => {
  if (!canManageGuests.value) return
  revokePreview(facePhotoPreview)
  revokePreview(bodyPhotoPreview)
  if (faceFileInput.value) faceFileInput.value.value = ''
  if (bodyFileInput.value) bodyFileInput.value.value = ''

  const today = new Date()
  today.setHours(23, 59, 0, 0)
  const tzOffset = new Date().getTimezoneOffset() * 60000
  const localISOTime = new Date(today - tzOffset).toISOString().slice(0, 16)

  guestForm.value = {
    last_name: '',
    first_name: '',
    middle_name: '',
    employee_id: '',
    valid_until: localISOTime,
    facePhotoFile: null,
    bodyPhotoFile: null,
  }
  employeeDropdownOpen.value = false
  employeeSearchQuery.value = ''
  displayDialog.value = true
}

const closeDialog = () => {
  displayDialog.value = false
  employeeDropdownOpen.value = false
  employeeSearchQuery.value = ''
  revokePreview(facePhotoPreview)
  revokePreview(bodyPhotoPreview)
}

const saveGuest = async () => {
  if (!canManageGuests.value) return
  if (!guestForm.value.last_name || !guestForm.value.first_name || !guestForm.value.valid_until || !guestForm.value.employee_id) {
    ui.warn('Заполните обязательные поля: фамилия, имя, к кому пришли и срок действия')
    return
  }
  if (!guestForm.value.facePhotoFile) {
    ui.warn('Сделайте снимок лица с камеры или загрузите фото лица гостя.')
    return
  }

  try {
    const formData = new FormData()
    formData.append('last_name', guestForm.value.last_name)
    formData.append('first_name', guestForm.value.first_name)
    if (guestForm.value.middle_name) formData.append('middle_name', guestForm.value.middle_name)
    formData.append('employee_id', guestForm.value.employee_id)

    formData.append('valid_until', guestForm.value.valid_until)
    formData.append('face_photo', guestForm.value.facePhotoFile)
    if (guestForm.value.bodyPhotoFile) formData.append('body_photo', guestForm.value.bodyPhotoFile)

    await guestsApi.createGuest(formData)
    closeDialog()
    await loadData()
    ui.success('Гостевой пропуск выдан')
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Ошибка сохранения гостя'))
  }
}

const openBodyPhotoDialog = (guest) => {
  if (!canManageGuests.value) return
  bodyPhotoGuest.value = guest
  bodyEnrollmentFile.value = null
  revokePreview(bodyEnrollmentPreview)
  if (bodyEnrollmentInput.value) bodyEnrollmentInput.value.value = ''
  bodyPhotoDialogVisible.value = true
}

const closeBodyPhotoDialog = () => {
  bodyPhotoDialogVisible.value = false
  bodyPhotoGuest.value = null
  bodyEnrollmentFile.value = null
  revokePreview(bodyEnrollmentPreview)
}

const onBodyEnrollmentFileSelected = (event) => {
  const file = event.target.files[0]
  if (!file) return
  bodyEnrollmentFile.value = file
  revokePreview(bodyEnrollmentPreview)
  bodyEnrollmentPreview.value = URL.createObjectURL(file)
}

const saveGuestBodyPhoto = async () => {
  if (!bodyPhotoGuest.value || !bodyEnrollmentFile.value) return
  bodyPhotoSaving.value = true
  try {
    const formData = new FormData()
    formData.append('body_photo', bodyEnrollmentFile.value)
    await guestsApi.uploadBodyPhoto(bodyPhotoGuest.value.id, formData)
    closeBodyPhotoDialog()
    await loadData()
    ui.success('Фото полного роста сохранено, Re-ID активен')
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось сохранить фото полного роста'))
  } finally {
    bodyPhotoSaving.value = false
  }
}

const formatRouteJobStatus = (status) => {
  const labels = {
    queued: 'в очереди',
    processing: 'обработка',
    completed: 'завершено',
    failed: 'ошибка',
  }
  return labels[status] || status
}

const toDateTimeLocalValue = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 16)
  const offsetMs = date.getTimezoneOffset() * 60000
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16)
}

const formatTimestamp = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ru-RU')
}

const setDefaultRoutePeriod = () => {
  const now = new Date()
  const from = new Date(now.getTime() - 24 * 60 * 60 * 1000)
  routeTimeFrom.value = toDateTimeLocalValue(from)
  routeTimeTo.value = toDateTimeLocalValue(now)
}

const onRoutePlanImageLoad = () => {
  if (!routePlanImage.value) return
  routePlanMetrics.value = {
    naturalWidth: routePlanImage.value.naturalWidth || 1,
    naturalHeight: routePlanImage.value.naturalHeight || 1,
  }
}

const onRouteFloorChange = () => {
  routeResult.value = null
  routeJob.value = null
  routePlanVersion.value = Date.now()
  routePlanMetrics.value = { naturalWidth: 1, naturalHeight: 1 }
}

const clearRouteJobPolling = () => {
  if (routeJobPollTimer) {
    clearInterval(routeJobPollTimer)
    routeJobPollTimer = null
  }
}

const openRouteDialog = (guest) => {
  routeGuest.value = guest
  routeJob.value = null
  routeResult.value = null
  routeResultLoading.value = false
  routePlanVersion.value = Date.now()
  routePlanMetrics.value = { naturalWidth: 1, naturalHeight: 1 }
  setDefaultRoutePeriod()
  routeFloorId.value = floorOptions.value[0]?.id ? String(floorOptions.value[0].id) : ''
  routeDialogVisible.value = true
}

const closeRouteDialog = () => {
  clearRouteJobPolling()
  routeDialogVisible.value = false
  routeGuest.value = null
  routeJob.value = null
  routeJobLoading.value = false
  routeResultLoading.value = false
  routeResult.value = null
}

const buildRouteFromJournal = async () => {
  if (!routeGuest.value || !routeFloorId.value) return
  routeResultLoading.value = true
  try {
    const response = await guestRoutesApi.getGuestProbableRoute(routeFloorId.value, routeGuest.value.id, {
      time_from: routeTimeFrom.value,
      time_to: routeTimeTo.value,
    })
    routeResult.value = response.data
    routePlanVersion.value = Date.now()

    if (!response.data.events?.length) {
      ui.warn('За выбранный период событий не найдено')
    } else if ((response.data.warnings || []).length) {
      ui.warn('Маршрут построен с предупреждениями')
    } else {
      ui.success('Вероятный маршрут гостя построен')
    }
  } catch (error) {
    routeResult.value = null
    ui.error(ui.getErrorMessage(error, 'Не удалось построить маршрут гостя'))
  } finally {
    routeResultLoading.value = false
  }
}

const buildRouteForCompletedJob = async (job) => {
  routeFloorId.value = String(job.floor_id)
  routeTimeFrom.value = toDateTimeLocalValue(job.time_from)
  routeTimeTo.value = toDateTimeLocalValue(job.time_to)
  await buildRouteFromJournal()
}

const pollRouteJob = async (jobId) => {
  const response = await guestRoutesApi.getGuestRouteAnalysisJob(jobId)
  routeJob.value = response.data

  if (response.data.status === 'completed') {
    clearRouteJobPolling()
    routeJobLoading.value = false
    await buildRouteForCompletedJob(response.data)
  } else if (response.data.status === 'failed') {
    clearRouteJobPolling()
    routeJobLoading.value = false
    ui.error(response.data.error_message || 'Офлайн-анализ маршрута завершился с ошибкой')
  }
}

const startGuestRouteAnalysis = async () => {
  if (!routeGuest.value || !routeFloorId.value) return
  routeJobLoading.value = true
  routeJob.value = null
  routeResult.value = null
  clearRouteJobPolling()
  try {
    const response = await guestRoutesApi.createGuestRouteAnalysisJob(routeFloorId.value, routeGuest.value.id)
    routeJob.value = response.data
    routeJobPollTimer = setInterval(() => {
      void pollRouteJob(response.data.id).catch((error) => {
        clearRouteJobPolling()
        routeJobLoading.value = false
        ui.error(ui.getErrorMessage(error, 'Не удалось получить статус анализа маршрута'))
      })
    }, 2500)
    await pollRouteJob(response.data.id)
  } catch (error) {
    routeJobLoading.value = false
    ui.error(ui.getErrorMessage(error, 'Не удалось запустить анализ маршрута гостя'))
  }
}

const deactivateGuest = async (id) => {
  if (!canManageGuests.value) return
  const accepted = await ui.confirm({
    header: 'Аннулировать пропуск?',
    message: 'Гость больше не сможет пройти через турникет.',
    acceptLabel: 'Аннулировать',
    acceptSeverity: 'danger',
  })
  if (!accepted) return

  try {
    await guestsApi.deactivateGuest(id)
    await loadData()
    ui.success('Гостевой пропуск аннулирован')
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Ошибка при закрытии пропуска'))
  }
}

onMounted(() => {
  loadData()
})

onBeforeUnmount(() => {
  clearRouteJobPolling()
  revokePreview(facePhotoPreview)
  revokePreview(bodyPhotoPreview)
  revokePreview(bodyEnrollmentPreview)
})
</script>

<style scoped>
.page-container { background: transparent; height: 100%; display: flex; flex-direction: column; gap: 1.5rem; }
.header-actions { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-size: 1.75rem; font-weight: 700; color: #0f172a; margin: 0; }
.page-subtitle { margin: 0.35rem 0 0; color: #64748b; font-size: 0.95rem; }

.filters-bar { display: flex; gap: 1rem; flex-wrap: wrap; background: #ffffff; padding: 1rem; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.search-box { position: relative; flex: 1; min-width: 250px; }
.search-box i { position: absolute; left: 1rem; top: 50%; transform: translateY(-50%); color: #94a3b8; }
.search-box input { width: 100%; padding: 0.75rem 1rem 0.75rem 2.5rem; border-radius: 8px; border: 1px solid #cbd5e1; background: #f8fafc; font-size: 0.95rem; outline: none; transition: 0.2s; }
.search-box input:focus { border-color: #3b82f6; background: #ffffff; }

.filter-select { padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid #cbd5e1; background: #f8fafc; color: #334155; font-size: 0.95rem; outline: none; min-width: 180px; cursor: pointer; }
.filter-select:focus { border-color: #3b82f6; }

.cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.5rem; }
.employee-card { background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; padding: 1.5rem; transition: transform 0.2s, box-shadow 0.2s; position: relative; display: flex; flex-direction: column; }
.employee-card:hover { transform: translateY(-3px); box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08); }

.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem; }
.status-badge { padding: 0.35rem 0.75rem; border-radius: 999px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em; }
.status-badge.active { background: #dcfce7; color: #166534; }
.status-badge.blocked { background: #fee2e2; color: #991b1b; }
.card-actions { display: flex; gap: 0.25rem; }

.card-body { display: flex; flex-direction: column; align-items: center; text-align: center; }
.avatar-container { margin-bottom: 1rem; }
.avatar-placeholder { width: 90px; height: 90px; border-radius: 50%; background: #f1f5f9; color: #94a3b8; display: flex; align-items: center; justify-content: center; font-size: 2.5rem; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
.avatar-placeholder.large { width: 130px; height: 130px; font-size: 3.5rem; }
.avatar-img { width: 90px; height: 90px; border-radius: 50%; object-fit: cover; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
.avatar-img.large { width: 130px; height: 130px; }

.emp-name { margin: 0 0 0.25rem 0; color: #0f172a; font-size: 1.15rem; font-weight: 700; }
.emp-middle-name { margin: 0 0 1rem 0; color: #64748b; font-size: 0.9rem; min-height: 1.2rem; }

.guest-info { width: 100%; display: flex; flex-direction: column; gap: 0.5rem; background: #f8fafc; padding: 0.75rem; border-radius: 8px; border: 1px solid #e2e8f0; }
.info-row { display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; color: #475569; font-weight: 500; text-align: left; }
.info-row i { color: #3b82f6; font-size: 1rem; }
.info-row.expired { color: #ef4444; }
.info-row.expired i { color: #ef4444; }
.info-row.reid-row { color: #0f766e; }
.info-row.reid-row i { color: #0f766e; }

.empty-state { grid-column: 1 / -1; display: flex; flex-direction: column; align-items: center; padding: 4rem 2rem; color: #94a3b8; background: #ffffff; border-radius: 16px; border: 1px dashed #cbd5e1; }
.empty-icon { font-size: 3rem; margin-bottom: 1rem; color: #cbd5e1; }
.empty-state h3 { color: #334155; margin: 0 0 0.5rem 0; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: white; padding: 2rem; border-radius: 16px; width: 100%; max-height: 90vh; overflow-y: auto; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25); }
.wide-modal { max-width: 850px; }
.route-modal { max-width: min(1180px, calc(100vw - 2rem)); }

.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.modal-header h2 { margin: 0; font-size: 1.3rem; color: #0f172a; }

.modal-body-split { display: flex; gap: 2rem; align-items: flex-start; }

.photo-column { width: 280px; flex-shrink: 0; display: flex; flex-direction: column; gap: 1rem; background: #f8fafc; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; }
.form-column { flex: 1; }

.photo-upload-block { display: flex; flex-direction: column; gap: 0.75rem; padding: 0.9rem; border-radius: 12px; background: #ffffff; border: 1px solid #e2e8f0; }
.photo-block-title { color: #334155; font-size: 0.9rem; font-weight: 700; }
.avatar-preview { display: flex; justify-content: center; margin-bottom: 0.5rem; }
.body-preview .avatar-img,
.body-preview .avatar-placeholder { border-radius: 16px; }
.modal-preview { width: 220px; margin: 1rem auto; }

.capture-controls { display: flex; flex-direction: column; gap: 0.75rem; }
.control-label { font-size: 0.85rem; font-weight: 600; color: #475569; }

.divider { display: flex; align-items: center; text-align: center; color: #94a3b8; font-size: 0.8rem; margin: 0.5rem 0; }
.divider::before, .divider::after { content: ''; flex: 1; border-bottom: 1px solid #cbd5e1; }
.divider span { padding: 0 0.5rem; }

.full-width-btn { width: 100%; justify-content: center; }
.upload-btn { border: 1px dashed #cbd5e1; }
.hidden-input { display: none; }
.capture-hint { margin: 0; color: #64748b; font-size: 0.8rem; line-height: 1.35; }
.route-dialog-layout { display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 1.25rem; align-items: start; }
.route-controls-column, .route-map-column { min-width: 0; }
.route-time-grid { display: grid; grid-template-columns: 1fr; gap: 0.65rem; }
.route-time-grid .form-group, .route-time-grid .form-input { min-width: 0; }
.route-job-status { display: flex; flex-direction: column; gap: 0.45rem; padding: 0.9rem; border-radius: 12px; background: #f8fafc; border: 1px solid #e2e8f0; color: #334155; font-size: 0.9rem; }
.job-note { color: #64748b; font-size: 0.82rem; }
.job-error { color: #b91c1c; font-weight: 700; }
.job-warnings { display: flex; flex-direction: column; gap: 0.25rem; padding: 0.6rem; border-radius: 10px; background: #fffbeb; border: 1px solid #fde68a; color: #92400e; }
.route-result-warnings { margin-top: 0.75rem; }
.route-events-panel { margin-top: 0.85rem; padding: 0.85rem; border-radius: 14px; background: #f8fafc; border: 1px solid #e2e8f0; }
.route-events-title { display: flex; align-items: center; justify-content: space-between; color: #334155; font-size: 0.85rem; font-weight: 800; margin-bottom: 0.65rem; }
.route-events-title strong { min-width: 28px; height: 24px; padding: 0 0.45rem; border-radius: 999px; background: #dbeafe; color: #1d4ed8; display: inline-flex; align-items: center; justify-content: center; }
.route-events-list { display: flex; flex-direction: column; gap: 0.45rem; max-height: 230px; overflow-y: auto; padding-right: 0.25rem; }
.route-event-row { display: flex; align-items: center; gap: 0.6rem; padding: 0.55rem; border-radius: 10px; background: #ffffff; border: 1px solid #e2e8f0; }
.route-event-order { width: 26px; height: 26px; border-radius: 999px; background: #7c3aed; color: #ffffff; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; font-weight: 800; }
.route-event-camera { color: #0f172a; font-size: 0.92rem; font-weight: 800; }
.route-event-time { margin-top: 0.15rem; color: #64748b; font-size: 0.82rem; }
.route-empty-message { color: #94a3b8; font-size: 0.85rem; line-height: 1.35; }
.route-map-header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 0.75rem; }
.route-map-header div { display: flex; flex-direction: column; gap: 0.15rem; }
.route-map-header strong { color: #0f172a; font-size: 1rem; }
.route-map-header span { color: #64748b; font-size: 0.82rem; }
.route-map-status { padding: 0.25rem 0.55rem; border-radius: 999px; background: #eef2ff; color: #4338ca; font-weight: 800; font-size: 0.75rem; }
.route-plan-preview { position: relative; min-height: 500px; border-radius: 16px; background: #f8fafc; border: 1px solid #e2e8f0; overflow: hidden; display: flex; align-items: center; justify-content: center; }
.route-plan-image { width: 100%; height: 100%; object-fit: contain; pointer-events: none; }
.route-plan-overlay { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.route-camera-zone { fill: rgba(14, 165, 233, 0.16); stroke: rgba(2, 132, 199, 0.78); stroke-width: 3; }
.route-result-line { stroke: #7c3aed; stroke-width: 8; stroke-linecap: round; stroke-linejoin: round; filter: drop-shadow(0 3px 6px rgba(124, 58, 237, 0.36)); }
.route-direction-arrow { fill: #7c3aed; }
.route-event-marker circle { fill: #111827; stroke: #ffffff; stroke-width: 4; filter: drop-shadow(0 3px 5px rgba(15, 23, 42, 0.3)); }
.route-event-marker text { fill: #ffffff; font-size: 16px; font-weight: 800; pointer-events: none; }
.route-plan-empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; text-align: center; padding: 1rem; color: #94a3b8; font-weight: 700; background: #f8fafc; }
.overlay-empty { background: rgba(248, 250, 252, 0.68); }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
.form-group { display: flex; flex-direction: column; gap: 0.4rem; }
.form-group.full-width { grid-column: 1 / -1; }
.form-group label { font-size: 0.85rem; font-weight: 600; color: #475569; }
.required { color: #ef4444; }
.form-input { width: 100%; box-sizing: border-box; padding: 0.75rem 1rem; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 0.95rem; background: #ffffff; outline: none; }
.form-input:focus { border-color: #3b82f6; }
.placeholder-text { color: #94a3b8; }

.employee-select {
  position: relative;
}

.employee-select-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  text-align: left;
}

.employee-select-panel {
  position: absolute;
  top: calc(100% + 0.5rem);
  left: 0;
  right: 0;
  z-index: 20;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.12);
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  max-height: min(200px, 45vh);
  overflow: hidden;
}

.employee-search-box {
  position: relative;
  margin-bottom: 0.75rem;
  flex-shrink: 0;
}

.employee-search-box i {
  position: absolute;
  left: 0.85rem;
  top: 50%;
  transform: translateY(-50%);
  color: #94a3b8;
}

.employee-search-input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.7rem 0.9rem 0.7rem 2.4rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.92rem;
  outline: none;
}

.employee-search-input:focus {
  border-color: #3b82f6;
}

.employee-options-list {
  overflow-y: auto;
  min-height: 0;
  padding-right: 0.25rem;
}

.employee-option {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  padding: 0.7rem 0.85rem;
  border-radius: 8px;
  cursor: pointer;
  color: #334155;
  font-size: 0.94rem;
}

.employee-option:hover,
.employee-option.selected {
  background: #eff6ff;
  color: #1d4ed8;
}

.employee-option-empty {
  padding: 0.7rem 0.85rem;
  color: #94a3b8;
  font-size: 0.9rem;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 2rem; border-top: 1px solid #e2e8f0; padding-top: 1.5rem; }

.btn-primary, .btn-text { border: none; padding: 0.65rem 1.2rem; border-radius: 8px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; transition: 0.2s; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-primary:disabled { background: #94a3b8; cursor: not-allowed; }
.btn-text { background: transparent; color: #64748b; }
.btn-text:hover { background: #f1f5f9; color: #0f172a; }
.route-journal-btn { border: 1px solid #cbd5e1; color: #334155; }

.btn-icon { background: transparent; border: none; cursor: pointer; width: 32px; height: 32px; border-radius: 6px; color: #64748b; display: flex; align-items: center; justify-content: center; transition: 0.2s; }
.btn-icon:hover { background: #f1f5f9; color: #0f172a; }
.btn-icon.danger:hover { background: #fee2e2; color: #ef4444; }
.btn-icon.warning:hover { background: #fef3c7; color: #f59e0b; }

@media (max-width: 768px) {
  .modal-body-split { flex-direction: column; }
  .route-dialog-layout, .route-time-grid { grid-template-columns: 1fr; }
  .route-plan-preview { min-height: 340px; }
  .photo-column { width: 100%; box-sizing: border-box; }
  .form-grid { grid-template-columns: 1fr; }
}
</style>
