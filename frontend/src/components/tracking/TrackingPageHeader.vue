<template>
  <div class="header-panel">
    <div>
      <h1 class="page-title">План здания</h1>
      <p class="page-subtitle">Выбор здания, этажа, загрузка плана, расстановка камер и ручная разметка маршрутов.</p>
    </div>

    <div class="top-buttons">
      <button v-if="canEditPlan" class="btn-secondary" @click="$emit('open-building')">
        <i class="pi pi-building"></i> Новое здание
      </button>
      <button
        v-if="canEditPlan"
        class="btn-secondary"
        :disabled="!selectedBuildingId"
        @click="$emit('open-floor')"
      >
        <i class="pi pi-plus"></i> Новый этаж
      </button>
      <button
        v-if="canEditPlan"
        class="btn-secondary"
        :disabled="!selectedFloorId"
        @click="$emit('open-floor-plan')"
      >
        <i class="pi pi-image"></i> План этажа
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  canEditPlan: {
    type: Boolean,
    default: false,
  },
  selectedBuildingId: {
    type: String,
    default: '',
  },
  selectedFloorId: {
    type: String,
    default: '',
  },
})

defineEmits(['open-building', 'open-floor', 'open-floor-plan'])
</script>

<style scoped>
.header-panel {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.page-title {
  margin: 0;
  color: #0f172a;
  font-size: 1.5rem;
  font-weight: 600;
}

.page-subtitle {
  margin: 0.35rem 0 0;
  color: #64748b;
  font-size: 0.9rem;
}

.top-buttons {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1rem;
  border: none;
  border-radius: 8px;
  background: #eef2ff;
  color: #334155;
  font-weight: 600;
  cursor: pointer;
}

.btn-secondary:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

@media (max-width: 768px) {
  .header-panel {
    flex-direction: column;
  }
}
</style>
