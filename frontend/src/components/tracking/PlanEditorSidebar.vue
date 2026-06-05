<template>
  <div class="editor-sidebar">
    <h2>Настройка плана</h2>

    <div v-if="unassignedCameras.length > 0" class="unassigned-section">
      <h3>Свободные камеры</h3>
      <p class="instruction-small">Выберите камеру, чтобы разместить её на текущем этаже:</p>
      <div class="unassigned-list">
        <div v-for="cam in unassignedCameras" :key="cam.id" class="unassigned-card">
          <span class="cam-name-small">{{ cam.name }}</span>
          <button class="btn-secondary btn-sm" title="Добавить на план" @click="$emit('add-camera', cam)">
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

      <button class="btn-text btn-danger remove-btn" @click="$emit('remove-camera', activeCamera.id)">
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
          <button class="btn-secondary btn-sm" @click="$emit('start-zone-draft')">
            {{ selectedCameraHasZone ? 'Редактировать зону' : 'Задать зону' }}
          </button>
          <button
            class="btn-success btn-sm"
            :disabled="zoneSaving || editableZonePoints.length !== 4"
            @click="$emit('save-zone')"
          >
            Сохранить зону
          </button>
          <button class="btn-text btn-danger btn-sm" :disabled="!editableZonePoints.length" @click="$emit('reset-zone')">
            Сбросить
          </button>
          <button class="btn-text btn-danger btn-sm" :disabled="!selectedCameraHasZone" @click="$emit('delete-zone')">
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
</template>

<script setup>
/**
 * Боковая панель редактирования технической настройки плана.
 *
 * Здесь техник или super admin размещает камеры на этаже и задаёт зону
 * видимости выбранной камеры. Компонент не хранит собственную сложную логику
 * drag/drop: он показывает состояние, а действия отправляет в Tracking.vue,
 * где есть доступ к координатам SVG и сохранению в backend.
 */
defineProps({
  unassignedCameras: {
    type: Array,
    default: () => [],
  },
  activeCamera: {
    type: Object,
    default: null,
  },
  selectedCameraHasZone: {
    type: Boolean,
    default: false,
  },
  zoneDraftCameraId: {
    type: Number,
    default: null,
  },
  zoneDraftPoints: {
    type: Array,
    default: () => [],
  },
  zoneSaving: {
    type: Boolean,
    default: false,
  },
  editableZonePoints: {
    type: Array,
    default: () => [],
  },
})

defineEmits([
  'add-camera',
  'remove-camera',
  'start-zone-draft',
  'save-zone',
  'reset-zone',
  'delete-zone',
])

/** Отобразить относительную координату камеры `0..1` как процент. */
function formatPercent(value) {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—'
}
</script>

<style scoped>
.editor-sidebar {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  padding: 1rem;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.editor-sidebar h2 {
  margin: 0;
  color: #0f172a;
  font-size: 1.15rem;
}

.unassigned-section {
  margin-bottom: 1.5rem;
}

.unassigned-section h3 {
  margin: 0 0 0.5rem;
  color: #0f172a;
  font-size: 1.05rem;
}

.instruction-small {
  margin: 0 0 0.75rem;
  color: #64748b;
  font-size: 0.82rem;
  line-height: 1.3;
}

.unassigned-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 220px;
  padding-right: 0.25rem;
  overflow-y: auto;
}

.unassigned-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.55rem 0.8rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f1f5f9;
}

.cam-name-small {
  color: #334155;
  font-size: 0.88rem;
  font-weight: 600;
}

.btn-secondary,
.btn-success,
.btn-text {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
}

.btn-secondary {
  background: #eef2ff;
  color: #334155;
}

.btn-success {
  background: #10b981;
  color: #ffffff;
}

.btn-text {
  background: transparent;
  color: #64748b;
}

.btn-secondary:disabled,
.btn-success:disabled,
.btn-text:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.btn-sm {
  padding: 0.35rem 0.6rem;
  font-size: 0.85rem;
}

.btn-danger {
  color: #ef4444;
}

.btn-danger:hover:not(:disabled) {
  background: #fee2e2;
  color: #dc2626;
}

.remove-btn {
  width: 100%;
  margin-top: 1rem;
  padding: 0.65rem 1rem;
  border: 1px solid #fecaca;
}

.sidebar-divider {
  height: 1px;
  margin: 1.5rem 0;
  border: 0;
  background: #e2e8f0;
}

.active-cam-info {
  padding: 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.info-group {
  margin-bottom: 1rem;
}

.info-group.compact {
  margin-bottom: 0.8rem;
}

.info-group label {
  display: block;
  margin-bottom: 0.25rem;
  color: #64748b;
  font-size: 0.82rem;
}

.cam-name,
.cam-value {
  color: #0f172a;
  font-weight: 600;
}

.side-panel {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}

.side-panel h3 {
  margin: 0 0 0.65rem;
  color: #0f172a;
  font-size: 1rem;
}

.zone-editor-box {
  padding: 0.85rem;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.camera-card-meta {
  margin-top: 0.2rem;
  color: #64748b;
  font-size: 0.82rem;
}

.zone-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.empty-selection {
  margin: auto 0;
  text-align: center;
  color: #94a3b8;
}

.instruction {
  margin: 0;
  color: #475569;
  font-size: 0.9rem;
  line-height: 1.5;
}
</style>
