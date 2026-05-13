<template>
  <span class="ui-status-badge" :class="`ui-status-badge--${tone}`">
    <slot />
  </span>
</template>

<script setup>
defineProps({
  tone: {
    type: String,
    default: 'neutral',
    validator: (value) => ['neutral', 'info', 'success', 'warning', 'danger'].includes(value),
  },
})
</script>
