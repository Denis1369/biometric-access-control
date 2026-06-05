<template>
  <div class="ui-loading-state">
    <span class="ui-loading-state__icon">
      <i class="pi pi-spin pi-spinner"></i>
    </span>
    <div class="ui-loading-state__title">{{ title }}</div>
    <p v-if="description">{{ description }}</p>
  </div>
</template>

<script setup>
/**
 * Единое состояние загрузки.
 *
 * Компонент показывает пользователю, что данные ещё запрашиваются или фоновая
 * операция продолжается. Он используется вместо разрозненных спиннеров, чтобы
 * интерфейс одинаково объяснял ожидание в разных разделах.
 */
defineProps({
  title: {
    type: String,
    default: 'Загрузка...',
  },
  description: {
    type: String,
    default: '',
  },
})
</script>
