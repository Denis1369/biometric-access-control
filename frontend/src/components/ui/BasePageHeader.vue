<template>
  <div class="ui-page-header">
    <div>
      <h1 class="ui-page-header__title">{{ title }}</h1>
      <p v-if="subtitle" class="ui-page-header__subtitle">{{ subtitle }}</p>
    </div>

    <div v-if="$slots.actions" class="ui-page-header__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    required: true,
  },
  subtitle: {
    type: String,
    default: '',
  },
})
</script>
