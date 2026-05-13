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
