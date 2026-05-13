<template>
  <div class="ui-empty-state">
    <span class="ui-empty-state__icon">
      <i :class="icon"></i>
    </span>
    <div class="ui-empty-state__title">{{ title }}</div>
    <p v-if="description">{{ description }}</p>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  icon: {
    type: String,
    default: 'pi pi-inbox',
  },
  title: {
    type: String,
    default: 'Нет данных',
  },
  description: {
    type: String,
    default: '',
  },
})
</script>
