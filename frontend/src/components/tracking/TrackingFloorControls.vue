<template>
  <div class="filters-row">
    <div class="filter-group wide">
      <label>Здание</label>
      <select :value="selectedBuildingId" class="form-input" @change="updateBuilding">
        <option value="">Выберите здание...</option>
        <option v-for="building in buildings" :key="building.id" :value="String(building.id)">
          {{ building.name }}
        </option>
      </select>
    </div>

    <div class="filter-group wide">
      <label>Этаж</label>
      <select
        :value="selectedFloorId"
        class="form-input"
        :disabled="!selectedBuildingId || floorsLoading"
        @change="updateFloor"
      >
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
        :disabled="!selectedFloorId"
        @click="$emit('toggle-edit')"
      >
        <i class="pi pi-pencil"></i> Редактировать камеры
      </button>

      <template v-else-if="isEditMode">
        <button class="btn-text" @click="$emit('cancel-edit')">Отмена</button>
        <button class="btn-success" :disabled="savingPlan || !selectedFloorId" @click="$emit('save-plan')">
          <i class="pi pi-check"></i> {{ savingPlan ? 'Сохранение...' : 'Сохранить' }}
        </button>
      </template>
    </div>
  </div>
</template>

<script setup>
defineProps({
  buildings: {
    type: Array,
    default: () => [],
  },
  floors: {
    type: Array,
    default: () => [],
  },
  selectedBuildingId: {
    type: String,
    default: '',
  },
  selectedFloorId: {
    type: String,
    default: '',
  },
  floorsLoading: {
    type: Boolean,
    default: false,
  },
  canEditPlan: {
    type: Boolean,
    default: false,
  },
  isEditMode: {
    type: Boolean,
    default: false,
  },
  savingPlan: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:selectedBuildingId',
  'update:selectedFloorId',
  'toggle-edit',
  'cancel-edit',
  'save-plan',
])

function updateBuilding(event) {
  emit('update:selectedBuildingId', event.target.value)
}

function updateFloor(event) {
  emit('update:selectedFloorId', event.target.value)
}
</script>

<style scoped>
.filters-row {
  display: grid;
  grid-template-columns: minmax(190px, 1fr) minmax(190px, 1fr) auto;
  align-items: end;
  gap: 1rem;
  padding: 1rem 1.25rem;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.filter-group label {
  color: #475569;
  font-size: 0.85rem;
  font-weight: 600;
}

.filter-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.form-input {
  width: 100%;
  padding: 0.7rem 0.9rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #1e293b;
  font-size: 0.95rem;
}

.form-input:focus {
  border-color: #3b82f6;
  background: #ffffff;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
  outline: none;
}

.btn-primary,
.btn-success,
.btn-text {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1rem;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
}

.btn-primary {
  background: #3b82f6;
  color: #ffffff;
}

.btn-success {
  background: #10b981;
  color: #ffffff;
}

.btn-text {
  background: transparent;
  color: #64748b;
}

.btn-primary:disabled,
.btn-success:disabled,
.btn-text:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

@media (max-width: 1200px) {
  .filters-row {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 768px) {
  .filters-row {
    grid-template-columns: 1fr;
  }
}
</style>
