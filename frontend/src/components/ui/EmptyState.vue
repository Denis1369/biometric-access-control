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
/**
 * Состояние пустого результата.
 *
 * Используется, когда список загружен успешно, но данных для отображения нет:
 * например не найдено гостей по фильтру или справочник ещё не заполнен. Это
 * отличает нормальную пустоту от ошибки загрузки.
 */
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
