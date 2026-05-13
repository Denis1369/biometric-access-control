<template>
  <div class="guests-filters">
    <SearchInput
      class="guests-filters__search"
      :model-value="searchQuery"
      placeholder="Поиск по ФИО гостя или сотрудника..."
      @update:model-value="$emit('update:searchQuery', $event)"
    />

    <select
      class="guests-filters__select"
      :value="selectedStatus"
      @change="$emit('update:selectedStatus', $event.target.value)"
    >
      <option value="all">Все статусы</option>
      <option value="active">Только активные</option>
      <option value="expired">Истекшие / закрытые</option>
    </select>

    <select
      class="guests-filters__select"
      :value="sortBy"
      @change="$emit('update:sortBy', $event.target.value)"
    >
      <option value="newest">Сначала новые</option>
      <option value="oldest">Сначала старые</option>
      <option value="name">По алфавиту (ФИО)</option>
    </select>
  </div>
</template>

<script setup>
import SearchInput from '../ui/SearchInput.vue'

defineProps({
  searchQuery: {
    type: String,
    default: '',
  },
  selectedStatus: {
    type: String,
    default: 'active',
  },
  sortBy: {
    type: String,
    default: 'newest',
  },
})

defineEmits(['update:searchQuery', 'update:selectedStatus', 'update:sortBy'])
</script>

<style scoped>
.guests-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
}

.guests-filters__search {
  flex: 1;
  min-width: 250px;
}

.guests-filters__select {
  min-width: 180px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  padding: 0.75rem 1rem;
  font: inherit;
  font-size: 0.95rem;
  cursor: pointer;
}

.guests-filters__select:focus {
  outline: none;
  border-color: #3b82f6;
}
</style>
