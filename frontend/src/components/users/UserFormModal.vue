<template>
  <BaseModal
    :model-value="open"
    :title="isEditMode ? 'Редактировать пользователя' : 'Новый пользователь'"
    @update:model-value="$emit('update:open', $event)"
    @close="$emit('close')"
  >
    <div class="user-form-modal__grid">
      <div class="user-form-modal__group">
        <label>Логин <span class="user-form-modal__required">*</span></label>
        <input
          :value="username"
          type="text"
          class="user-form-modal__input"
          @input="$emit('update:username', $event.target.value)"
        />
      </div>

      <div class="user-form-modal__group">
        <label>Роль <span class="user-form-modal__required">*</span></label>
        <select
          :value="role"
          class="user-form-modal__input"
          @change="$emit('update:role', $event.target.value)"
        >
          <option v-for="option in roleOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </div>

      <div class="user-form-modal__group user-form-modal__group--full">
        <label>Привязать к сотруднику</label>
        <select
          :value="employeeId ? String(employeeId) : ''"
          class="user-form-modal__input"
          @change="handleEmployeeChange"
        >
          <option value="">Не привязывать</option>
          <option v-for="employee in availableEmployees" :key="employee.id" :value="String(employee.id)">
            {{ employee.full_name }}
          </option>
        </select>
      </div>

      <div class="user-form-modal__group user-form-modal__group--full">
        <label>
          {{ isEditMode ? 'Новый пароль' : 'Пароль' }}
          <span v-if="!isEditMode" class="user-form-modal__required">*</span>
        </label>
        <input
          :value="password"
          type="password"
          class="user-form-modal__input"
          @input="$emit('update:password', $event.target.value)"
        />
        <small class="user-form-modal__hint">
          {{ isEditMode ? 'Оставь пустым, если пароль менять не нужно.' : 'Минимум 6 символов.' }}
        </small>
      </div>
    </div>

    <div class="user-form-modal__group user-form-modal__checkbox">
      <input
        id="userActive"
        :checked="isActive"
        type="checkbox"
        @change="$emit('update:isActive', $event.target.checked)"
      />
      <label for="userActive">Учетная запись активна</label>
    </div>

    <template #footer>
      <BaseButton variant="text" @click="$emit('close')">Отмена</BaseButton>
      <BaseButton @click="$emit('save')">Сохранить</BaseButton>
    </template>
  </BaseModal>
</template>

<script setup>
import BaseButton from '../ui/BaseButton.vue'
import BaseModal from '../ui/BaseModal.vue'

/**
 * Форма создания и редактирования учётной записи.
 *
 * Компонент не обращается к API напрямую. Он только отображает поля и сообщает
 * родительской странице об изменениях через `update:*`. Такой подход оставляет
 * всю бизнес-логику в `Users.vue`: проверку роли, сохранение пользователя,
 * привязку к сотруднику и обновление списка после ответа backend.
 */
defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  isEditMode: {
    type: Boolean,
    default: false,
  },
  username: {
    type: String,
    default: '',
  },
  password: {
    type: String,
    default: '',
  },
  role: {
    type: String,
    default: 'checkpoint_operator',
  },
  isActive: {
    type: Boolean,
    default: true,
  },
  employeeId: {
    type: Number,
    default: null,
  },
  roleOptions: {
    type: Array,
    default: () => [],
  },
  availableEmployees: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits([
  'update:open',
  'update:username',
  'update:password',
  'update:role',
  'update:isActive',
  'update:employeeId',
  'close',
  'save',
])

function handleEmployeeChange(event) {
  const value = event.target.value
  emit('update:employeeId', value ? Number(value) : null)
}
</script>

<style scoped>
.user-form-modal__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.user-form-modal__group {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.user-form-modal__group--full {
  grid-column: 1 / -1;
}

.user-form-modal__input {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 0.75rem 0.9rem;
  background: #f8fafc;
}

.user-form-modal__hint {
  color: #64748b;
  font-size: 0.8rem;
}

.user-form-modal__required {
  color: #ef4444;
}

.user-form-modal__checkbox {
  margin-top: 1rem;
  flex-direction: row;
  align-items: center;
  gap: 0.6rem;
}

@media (max-width: 640px) {
  .user-form-modal__grid {
    grid-template-columns: 1fr;
  }
}
</style>
