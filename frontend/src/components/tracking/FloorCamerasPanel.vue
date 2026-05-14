<template>
  <div class="logs-section workspace-panel">
    <div class="section-header">
      <div>
        <h2>Камеры этажа</h2>
        <p>Размещённые камеры и их зоны видимости.</p>
      </div>
      <span class="item-count">{{ mappedCameras.length }}</span>
    </div>

    <div class="panel-body">
      <div class="panel-intro">
        <div>
          <strong>{{ mappedCameras.length }}</strong>
          камер размещено на плане
        </div>
        <span>{{ selectedFloorLabel || 'Этаж не выбран' }}</span>
      </div>

      <div class="logs-list camera-list-panel">
        <div
          v-for="camera in mappedCameras"
          :key="camera.id"
          :class="['camera-card', { selected: activeCameraId === camera.id }]"
          @click="$emit('camera-click', camera)"
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
    </div>
  </div>
</template>

<script setup>
defineProps({
  mappedCameras: {
    type: Array,
    default: () => [],
  },
  activeCameraId: {
    type: [Number, String],
    default: null,
  },
  cameraZonesByCameraId: {
    type: Map,
    required: true,
  },
  selectedFloorLabel: {
    type: String,
    default: '',
  },
})

defineEmits(['camera-click'])

function formatPercent(value) {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—'
}
</script>

<style scoped>
.logs-section {
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

.workspace-panel {
  gap: 0.85rem;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.section-header h2 {
  margin: 0;
  color: #0f172a;
  font-size: 1.15rem;
}

.section-header p {
  margin: 0.25rem 0 0;
  color: #64748b;
  font-size: 0.85rem;
}

.item-count {
  min-width: 34px;
  height: 28px;
  padding: 0 0.6rem;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
}

.panel-body {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
}

.panel-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.85rem;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  background: linear-gradient(135deg, #eff6ff, #f8fafc);
  color: #334155;
  font-size: 0.88rem;
}

.panel-intro strong {
  margin-right: 0.25rem;
  color: #1d4ed8;
  font-size: 1.2rem;
}

.panel-intro span {
  color: #64748b;
  font-size: 0.8rem;
  text-align: right;
}

.logs-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 0.75rem;
  height: 0;
  margin-top: 1rem;
  padding-right: 0.5rem;
  overflow-y: auto;
}

.camera-list-panel {
  min-height: 260px;
}

.camera-card {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.8rem 0.9rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  cursor: pointer;
}

.camera-card:hover {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.camera-card.selected {
  border-color: #10b981;
  background: #ecfdf5;
}

.camera-card-icon {
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: #dbeafe;
  color: #2563eb;
  display: flex;
  align-items: center;
  justify-content: center;
}

.camera-card-name {
  color: #0f172a;
  font-weight: 700;
}

.camera-card-meta {
  margin-top: 0.2rem;
  color: #64748b;
  font-size: 0.82rem;
}

.camera-card-meta.zone-ready {
  color: #059669;
  font-weight: 700;
}

.empty-logs {
  margin: auto 0;
  text-align: center;
  color: #94a3b8;
}
</style>
