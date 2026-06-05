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
/**
 * Общий заголовок страницы.
 *
 * Компонент задаёт одинаковую структуру для крупных разделов: название,
 * поясняющий подзаголовок и область действий справа. Благодаря этому страницы
 * справочников, гостей и плана здания визуально читаются как единая система.
 */
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
