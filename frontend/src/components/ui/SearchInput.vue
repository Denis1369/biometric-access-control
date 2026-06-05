<template>
  <label class="ui-search">
    <i class="pi pi-search ui-search__icon"></i>
    <input
      class="ui-search__input"
      type="search"
      :value="modelValue"
      :placeholder="placeholder"
      @input="$emit('update:modelValue', $event.target.value)"
    />
  </label>
</template>

<script setup>
/**
 * Универсальное поле поиска.
 *
 * Компонент является управляемым input-ом: значение приходит через
 * `modelValue`, а каждое изменение отправляется наружу событием
 * `update:modelValue`. Поэтому родительская страница сама решает, как
 * фильтровать данные и нужно ли сохранять поисковый запрос.
 */
defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  placeholder: {
    type: String,
    default: 'Поиск',
  },
})

defineEmits(['update:modelValue'])
</script>
