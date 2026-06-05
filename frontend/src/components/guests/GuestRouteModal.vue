<template>
  <div v-if="open" class="modal-overlay" @click.self="close">
    <div class="modal-content route-modal">
      <div class="modal-header">
        <h2>Маршрут гостя</h2>
        <button class="btn-icon close-btn" @click="close">
          <i class="pi pi-times"></i>
        </button>
      </div>

      <p class="capture-hint">
        Гость: {{ formatGuestName(guest) }}. Можно мгновенно построить маршрут по уже записанному журналу
        или сначала проанализировать file-видео камер выбранного этажа.
      </p>

      <div class="route-dialog-layout">
        <div class="route-controls-column">
          <div class="form-group">
            <label>Этаж <span class="required">*</span></label>
            <select
              :value="floorId"
              class="form-input"
              :disabled="jobLoading"
              @change="handleFloorChange"
            >
              <option value="" disabled>Выберите этаж...</option>
              <option v-for="floor in floorOptions" :key="floor.id" :value="String(floor.id)">
                {{ floor.label }}
              </option>
            </select>
          </div>

          <div class="route-period-card">
            <div class="route-period-title">Период поиска</div>
            <div class="route-period-row">
              <div class="form-group">
                <label>Дата от</label>
                <input
                  :value="dateFrom"
                  class="form-input"
                  type="date"
                  :disabled="jobLoading"
                  @input="$emit('update:dateFrom', $event.target.value)"
                />
              </div>
              <div class="form-group time-field">
                <label>Время от</label>
                <input
                  :value="clockFrom"
                  class="form-input"
                  type="time"
                  :disabled="jobLoading"
                  @input="$emit('update:clockFrom', $event.target.value)"
                />
              </div>
            </div>
            <div class="route-period-row">
              <div class="form-group">
                <label>Дата до</label>
                <input
                  :value="dateTo"
                  class="form-input"
                  type="date"
                  :disabled="jobLoading"
                  @input="$emit('update:dateTo', $event.target.value)"
                />
              </div>
              <div class="form-group time-field">
                <label>Время до</label>
                <input
                  :value="clockTo"
                  class="form-input"
                  type="time"
                  :disabled="jobLoading"
                  @input="$emit('update:clockTo', $event.target.value)"
                />
              </div>
            </div>
          </div>

          <div v-if="job" class="route-job-status">
            <div><b>Статус:</b> {{ formatRouteJobStatus(job.status) }}</div>
            <div><b>Обработано камер:</b> {{ job.processed_cameras }} из {{ job.total_cameras ?? '—' }}</div>
            <div><b>Событий найдено:</b> {{ job.events_written }}</div>
            <div v-if="job.status === 'processing' && job.processed_cameras === 0" class="job-note">
              Первая камера ещё обрабатывается. Счётчик увеличится после завершения анализа этой камеры.
            </div>
            <div v-if="job.error_message" class="job-error">{{ job.error_message }}</div>
            <div v-if="jobWarnings.length" class="job-warnings">
              <div v-for="warning in jobWarnings" :key="warning">{{ warning }}</div>
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
            <span v-if="resultLoading" class="route-map-status">Построение...</span>
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
            <div v-else-if="!result && !resultLoading" class="route-plan-empty overlay-empty">
              Нажмите «Построить по журналу» или «Проанализировать видео и построить».
            </div>
          </div>
        </div>
      </div>

      <div class="modal-actions">
        <button class="btn-text" @click="close">Отмена</button>
        <button
          v-if="canBuildFromJournal"
          class="btn-text route-journal-btn"
          :disabled="!floorId || jobLoading || resultLoading"
          @click="$emit('build-from-journal')"
        >
          Построить по журналу
        </button>
        <button
          v-if="canStartAnalysis"
          class="btn-primary"
          :disabled="!floorId || jobLoading || resultLoading"
          @click="$emit('start-analysis')"
        >
          {{ jobLoading ? 'Анализ...' : 'Проанализировать видео и построить' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { floorsApi } from '../../api/floors'
import { formatPolygonPoints, polygonCentroid } from '../../services/geometry'

/**
 * Модальное окно построения маршрута гостя.
 *
 * Компонент намеренно живёт в разделе гостей: пользователь выбирает конкретного
 * гостя и строит его маршрут за день/период. Внутри есть два сценария:
 * мгновенно построить маршрут по уже записанному журналу или запустить тяжёлый
 * offline-анализ file-видео камер, дождаться job и показать полученный маршрут.
 */
const props = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  guest: {
    type: Object,
    default: null,
  },
  floorId: {
    type: String,
    default: '',
  },
  floorOptions: {
    type: Array,
    default: () => [],
  },
  job: {
    type: Object,
    default: null,
  },
  jobLoading: {
    type: Boolean,
    default: false,
  },
  resultLoading: {
    type: Boolean,
    default: false,
  },
  result: {
    type: Object,
    default: null,
  },
  dateFrom: {
    type: String,
    default: '',
  },
  clockFrom: {
    type: String,
    default: '',
  },
  dateTo: {
    type: String,
    default: '',
  },
  clockTo: {
    type: String,
    default: '',
  },
  canBuildFromJournal: {
    type: Boolean,
    default: false,
  },
  canStartAnalysis: {
    type: Boolean,
    default: false,
  },
})

/**
 * События оставляют бизнес-логику на родительской странице Guests.vue.
 *
 * Модалка отвечает за отображение формы, карты и результата, но не решает сама,
 * можно ли запускать анализ, как показывать ошибки и когда обновлять список
 * гостей. Поэтому действия пользователя пробрасываются наружу через emit.
 */
const emit = defineEmits([
  'update:open',
  'update:floorId',
  'update:dateFrom',
  'update:clockFrom',
  'update:dateTo',
  'update:clockTo',
  'close',
  'floor-change',
  'build-from-journal',
  'start-analysis',
])

/**
 * Ссылка на изображение плана и его натуральный размер.
 *
 * SVG-слой маршрута использует viewBox исходного изображения плана. Если взять
 * размер картинки на экране, стрелки и зоны камер съедут при изменении масштаба
 * модального окна.
 */
const routePlanImage = ref(null)
const routePlanVersion = ref(Date.now())
const routePlanMetrics = ref({
  naturalWidth: 1,
  naturalHeight: 1,
})

const selectedFloor = computed(() =>
  props.floorOptions.find(floor => String(floor.id) === String(props.floorId)) || null
)

/**
 * URL плана этажа с cache-busting параметром.
 *
 * Версия обновляется при открытии модалки, смене этажа или результата, чтобы
 * браузер не показывал старую картинку после изменения плана.
 */
const routePlanUrl = computed(() => {
  if (!selectedFloor.value?.has_plan || !props.floorId) return ''
  const baseUrl = floorsApi.getFloorPlanUrl(props.floorId)
  const separator = baseUrl.includes('?') ? '&' : '?'
  return `${baseUrl}${separator}v=${routePlanVersion.value}`
})

/** ViewBox SVG-слоя в координатах оригинального изображения плана. */
const routePlanViewBox = computed(() => {
  const { naturalWidth, naturalHeight } = routePlanMetrics.value
  return `0 0 ${naturalWidth || 1} ${naturalHeight || 1}`
})

/** Polyline вероятного маршрута, которую backend уже вернул в координатах плана. */
const routePolyline = computed(() =>
  (props.result?.route_nodes || []).map(node => `${node.x},${node.y}`).join(' ')
)

/** Зоны камер, участвующих в построенном маршруте. */
const routeCameraZones = computed(() => props.result?.camera_zones || [])
/** События камер в порядке timestamp: именно они задают направление движения. */
const routeEvents = computed(() => props.result?.events || [])
/** Предупреждения backend-а: нет зоны, зона не пересекает граф, путь не найден и т.д. */
const routeWarnings = computed(() => props.result?.warnings || [])
const jobWarnings = computed(() => {
  const warnings = props.job?.warnings || []
  const routeWarningSet = new Set(routeWarnings.value)
  return warnings.filter(warning => !routeWarningSet.has(warning))
})
/** Размер маркера события масштабируется от ширины плана, чтобы номер был читаемым. */
const routeMarkerRadius = computed(() => Math.max(9, routePlanMetrics.value.naturalWidth / 115))

/**
 * Маркеры событий на карте.
 *
 * Если backend вернул `route_anchor`, номер события ставится прямо на точку
 * пересечения зоны камеры с графом маршрута. Если якоря нет, используется центр
 * полигона зоны камеры как более грубая, но понятная fallback-позиция.
 */
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

/**
 * При смене входных данных сбрасываем размеры плана.
 *
 * Это заставляет SVG пересчитать viewBox после загрузки нового изображения,
 * иначе старая ширина/высота может остаться от предыдущего этажа.
 */
watch(
  () => [props.open, props.floorId, props.result],
  () => {
    routePlanVersion.value = Date.now()
    routePlanMetrics.value = { naturalWidth: 1, naturalHeight: 1 }
  }
)

/** Закрыть модальное окно и сообщить родителю, что сценарий завершён. */
function close() {
  emit('update:open', false)
  emit('close')
}

/** Передать выбранный этаж родителю, чтобы он мог загрузить план и маршрут. */
function handleFloorChange(event) {
  emit('update:floorId', event.target.value)
  emit('floor-change')
}

/** Собрать ФИО гостя для поясняющего текста в шапке модалки. */
function formatGuestName(guest) {
  if (!guest) return ''
  return [guest.last_name, guest.first_name, guest.middle_name].filter(Boolean).join(' ')
}

/** Перевести технический статус backend job в подпись для оператора. */
function formatRouteJobStatus(status) {
  const labels = {
    queued: 'в очереди',
    processing: 'обработка',
    completed: 'завершено',
    failed: 'ошибка',
  }
  return labels[status] || status
}

/** Отформатировать timestamp события камеры в привычный русский формат даты/времени. */
function formatTimestamp(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ru-RU')
}

/** Запомнить натуральный размер плана после загрузки изображения. */
function onRoutePlanImageLoad() {
  if (!routePlanImage.value) return
  routePlanMetrics.value = {
    naturalWidth: routePlanImage.value.naturalWidth || 1,
    naturalHeight: routePlanImage.value.naturalHeight || 1,
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(4px);
}

.modal-content {
  width: 100%;
  max-height: 90vh;
  padding: 2rem;
  overflow-y: auto;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.modal-header h2 {
  margin: 0;
  color: #0f172a;
  font-size: 1.3rem;
}

.capture-hint {
  margin: 0;
  color: #64748b;
  font-size: 0.8rem;
  line-height: 1.35;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.form-group label {
  color: #475569;
  font-size: 0.85rem;
  font-weight: 600;
}

.required {
  color: #ef4444;
}

.form-input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.75rem 1rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  color: #0f172a;
  font-size: 0.95rem;
  outline: none;
}

.form-input:focus {
  border-color: #3b82f6;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid #e2e8f0;
}

.btn-primary,
.btn-text {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.65rem 1.2rem;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: 0.2s;
}

.btn-primary {
  color: #ffffff;
  background: #3b82f6;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-primary:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.btn-text {
  color: #64748b;
  background: transparent;
}

.btn-text:hover:not(:disabled) {
  color: #0f172a;
  background: #f1f5f9;
}

.btn-text:disabled {
  color: #94a3b8;
  cursor: not-allowed;
}

.btn-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 6px;
  color: #64748b;
  background: transparent;
  cursor: pointer;
  transition: 0.2s;
}

.btn-icon:hover {
  color: #0f172a;
  background: #f1f5f9;
}

.route-modal {
  max-width: min(1180px, calc(100vw - 2rem));
}

.route-dialog-layout {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 1.25rem;
  align-items: start;
}

.route-controls-column,
.route-map-column {
  min-width: 0;
}

.route-period-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.85rem;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
}

.route-period-title {
  color: #334155;
  font-size: 0.85rem;
  font-weight: 800;
}

.route-period-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 124px;
  gap: 0.65rem;
  align-items: end;
}

.route-period-row .form-group,
.route-period-row .form-input {
  min-width: 0;
}

.time-field .form-input {
  text-align: center;
}

.route-job-status {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  padding: 0.9rem;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #334155;
  font-size: 0.9rem;
}

.job-note {
  color: #64748b;
  font-size: 0.82rem;
}

.job-error {
  color: #b91c1c;
  font-weight: 700;
}

.job-warnings {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.6rem;
  border-radius: 10px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
}

.route-result-warnings {
  margin-top: 0.75rem;
}

.route-events-panel {
  margin-top: 0.85rem;
  padding: 0.85rem;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.route-events-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #334155;
  font-size: 0.85rem;
  font-weight: 800;
  margin-bottom: 0.65rem;
}

.route-events-title strong {
  min-width: 28px;
  height: 24px;
  padding: 0 0.45rem;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.route-events-list {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  max-height: 230px;
  overflow-y: auto;
  padding-right: 0.25rem;
}

.route-event-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
}

.route-event-order {
  width: 26px;
  height: 26px;
  border-radius: 999px;
  background: #7c3aed;
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-weight: 800;
}

.route-event-camera {
  color: #0f172a;
  font-size: 0.92rem;
  font-weight: 800;
}

.route-event-time {
  margin-top: 0.15rem;
  color: #64748b;
  font-size: 0.82rem;
}

.route-empty-message {
  color: #94a3b8;
  font-size: 0.85rem;
  line-height: 1.35;
}

.route-map-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.route-map-header div {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.route-map-header strong {
  color: #0f172a;
  font-size: 1rem;
}

.route-map-header span {
  color: #64748b;
  font-size: 0.82rem;
}

.route-map-status {
  padding: 0.25rem 0.55rem;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-weight: 800;
  font-size: 0.75rem;
}

.route-plan-preview {
  position: relative;
  min-height: 500px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.route-plan-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.route-plan-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.route-camera-zone {
  fill: rgba(14, 165, 233, 0.16);
  stroke: rgba(2, 132, 199, 0.78);
  stroke-width: 3;
}

.route-result-line {
  stroke: #7c3aed;
  stroke-width: 8;
  stroke-linecap: round;
  stroke-linejoin: round;
  filter: drop-shadow(0 3px 6px rgba(124, 58, 237, 0.36));
}

.route-direction-arrow {
  fill: #7c3aed;
}

.route-event-marker circle {
  fill: #111827;
  stroke: #ffffff;
  stroke-width: 4;
  filter: drop-shadow(0 3px 5px rgba(15, 23, 42, 0.3));
}

.route-event-marker text {
  fill: #ffffff;
  font-size: 16px;
  font-weight: 800;
  pointer-events: none;
}

.route-plan-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 1rem;
  color: #94a3b8;
  font-weight: 700;
  background: #f8fafc;
}

.overlay-empty {
  background: rgba(248, 250, 252, 0.68);
}

.route-journal-btn {
  border: 1px solid #cbd5e1;
  color: #334155;
}

@media (max-width: 768px) {
  .route-dialog-layout,
  .route-period-row {
    grid-template-columns: 1fr;
  }

  .route-plan-preview {
    min-height: 340px;
  }
}
</style>
