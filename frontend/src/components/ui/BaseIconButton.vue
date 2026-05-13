<template>
  <button
    class="ui-icon-button"
    :class="toneClass"
    :type="type"
    :disabled="disabled"
    :aria-label="label"
    :title="label"
  >
    <i v-if="icon" :class="icon"></i>
    <slot v-else />
  </button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  icon: {
    type: String,
    default: '',
  },
  label: {
    type: String,
    required: true,
  },
  tone: {
    type: String,
    default: 'neutral',
    validator: (value) => ['neutral', 'warning', 'danger'].includes(value),
  },
  type: {
    type: String,
    default: 'button',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const toneClass = computed(() => (props.tone === 'neutral' ? '' : `ui-icon-button--${props.tone}`))
</script>
