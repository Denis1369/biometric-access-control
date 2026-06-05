<template>
  <button
    class="ui-button"
    :class="buttonClasses"
    :type="type"
    :disabled="disabled"
  >
    <slot />
  </button>
</template>

<script setup>
import { computed } from 'vue'

/**
 * Базовая кнопка приложения.
 *
 * Компонент задаёт единый набор вариантов, размеров и состояния disabled для
 * всех страниц. За счёт этого новые разделы не создают свои случайные стили
 * кнопок, а используют общий визуальный язык интерфейса СКУД.
 */
const props = defineProps({
  type: {
    type: String,
    default: 'button',
  },
  variant: {
    type: String,
    default: 'primary',
    validator: (value) => ['primary', 'secondary', 'text', 'danger', 'success'].includes(value),
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md'].includes(value),
  },
  block: {
    type: Boolean,
    default: false,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const buttonClasses = computed(() => [
  `ui-button--${props.variant}`,
  `ui-button--${props.size}`,
  { 'ui-button--block': props.block },
])
</script>
