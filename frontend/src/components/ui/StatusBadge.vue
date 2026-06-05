<template>
  <span class="ui-status-badge" :class="`ui-status-badge--${tone}`">
    <slot />
  </span>
</template>

<script setup>
/**
 * Маленький статусный бейдж.
 *
 * Используется для состояний вроде “активен”, “отключена”, “ошибка” или
 * “готово”. `tone` выбирает цветовую семантику, а текст передаётся через slot,
 * чтобы один компонент подходил для разных справочников и карточек.
 */
defineProps({
  tone: {
    type: String,
    default: 'neutral',
    validator: (value) => ['neutral', 'info', 'success', 'warning', 'danger'].includes(value),
  },
})
</script>
