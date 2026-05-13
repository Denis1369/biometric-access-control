<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="ui-modal-overlay"
      @click.self="handleBackdropClick"
    >
      <section
        class="ui-modal"
        :class="`ui-modal--${size}`"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
      >
        <header class="ui-modal__header">
          <h2 :id="titleId" class="ui-modal__title">{{ title }}</h2>
          <BaseIconButton icon="pi pi-times" label="Закрыть" @click="close" />
        </header>

        <div class="ui-modal__body">
          <slot />
        </div>

        <footer v-if="$slots.footer" class="ui-modal__footer">
          <slot name="footer" />
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import BaseIconButton from './BaseIconButton.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    required: true,
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md', 'lg', 'xl'].includes(value),
  },
  closeOnBackdrop: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['update:modelValue', 'close'])

const titleId = computed(() => `modal-title-${props.title.toLowerCase().replace(/[^a-zа-я0-9]+/giu, '-')}`)

function close() {
  emit('update:modelValue', false)
  emit('close')
}

function handleBackdropClick() {
  if (props.closeOnBackdrop) close()
}
</script>
