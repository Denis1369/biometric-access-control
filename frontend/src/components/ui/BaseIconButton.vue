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

/**
 * Кнопка-иконка для компактных действий в карточках и списках.
 *
 * Обязательный `label` используется сразу для `aria-label` и `title`, поэтому
 * такая кнопка остаётся понятной для экранных читалок и для пользователя при
 * наведении мыши. Это особенно важно в карточках гостей и камер, где действия
 * часто представлены только пиктограммами.
 */
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
