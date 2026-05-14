<template>
  <div class="route-toolbar">
    <button
      v-if="canEditPlan"
      class="mode-button"
      :class="{ active: graphMode === 'markup' }"
      :disabled="!routeGraphAvailable || isEditMode || routeGraphLoading"
      @click="$emit('set-graph-mode', 'markup')"
    >
      Режим разметки
    </button>
    <button
      class="mode-button"
      :class="{ active: graphMode === 'path' }"
      :disabled="!routeGraphAvailable || isEditMode || routeGraphLoading"
      @click="$emit('set-graph-mode', 'path')"
    >
      Режим маршрута
    </button>
    <button class="btn-text btn-compact" :disabled="!routePathCount" @click="$emit('clear-route-path')">
      Очистить маршрут
    </button>
    <button
      v-if="canEditPlan"
      class="btn-text btn-danger btn-compact"
      :disabled="!nodeCount && !edgeCount"
      @click="$emit('clear-route-graph')"
    >
      Очистить граф
    </button>
    <span class="graph-counter">
      {{ routeGraphLoading ? 'Загрузка графа...' : `Точек: ${nodeCount} · Линий: ${edgeCount}` }}
    </span>
  </div>
</template>

<script setup>
defineProps({
  canEditPlan: {
    type: Boolean,
    default: false,
  },
  graphMode: {
    type: String,
    default: 'markup',
  },
  routeGraphAvailable: {
    type: Boolean,
    default: false,
  },
  isEditMode: {
    type: Boolean,
    default: false,
  },
  routeGraphLoading: {
    type: Boolean,
    default: false,
  },
  nodeCount: {
    type: Number,
    default: 0,
  },
  edgeCount: {
    type: Number,
    default: 0,
  },
  routePathCount: {
    type: Number,
    default: 0,
  },
})

defineEmits(['set-graph-mode', 'clear-route-path', 'clear-route-graph'])
</script>

<style scoped>
.route-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  padding: 0.65rem;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.mode-button {
  padding: 0.45rem 0.75rem;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #ffffff;
  color: #334155;
  font-weight: 700;
  cursor: pointer;
}

.mode-button.active {
  border-color: #0891b2;
  background: #cffafe;
  color: #155e75;
}

.mode-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.btn-text {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  font-weight: 600;
  cursor: pointer;
}

.btn-text:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.btn-compact {
  padding: 0.45rem 0.65rem;
}

.btn-danger {
  color: #ef4444;
}

.btn-danger:hover:not(:disabled) {
  background: #fee2e2;
  color: #dc2626;
}

.graph-counter {
  margin-left: auto;
  color: #475569;
  font-size: 0.85rem;
  font-weight: 700;
}
</style>
