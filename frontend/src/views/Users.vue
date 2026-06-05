<template>
  <div class="page-container">
    <BasePageHeader
      title="Пользователи системы"
      subtitle="Создание учетных записей для super admin и операторов КПП."
    >
      <template #actions>
        <BaseButton @click="openCreateDialog">
          <i class="pi pi-plus"></i> Новый пользователь
        </BaseButton>
      </template>
    </BasePageHeader>

    <div class="table-card">
      <table class="users-table">
        <thead>
          <tr>
            <th>Логин</th>
            <th>Роль</th>
            <th>Сотрудник</th>
            <th>Статус</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.username }}</td>
            <td>
              <StatusBadge tone="info">{{ roleLabels[user.role] || user.role }}</StatusBadge>
            </td>
            <td>{{ user.employee_name || 'Не привязан' }}</td>
            <td>
              <StatusBadge :tone="user.is_active ? 'success' : 'danger'">
                {{ user.is_active ? 'Активен' : 'Отключен' }}
              </StatusBadge>
            </td>
            <td>
              <BaseIconButton
                icon="pi pi-pencil"
                label="Редактировать"
                tone="warning"
                @click="openEditDialog(user)"
              />
            </td>
          </tr>
          <tr v-if="users.length === 0">
            <td colspan="5" class="empty-cell">Пользователи пока не созданы.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <UserFormModal
      v-model:open="displayDialog"
      v-model:username="form.username"
      v-model:password="form.password"
      v-model:role="form.role"
      v-model:is-active="form.is_active"
      v-model:employee-id="form.employee_id"
      :is-edit-mode="isEditMode"
      :role-options="roleOptions"
      :available-employees="availableEmployees"
      @close="closeDialog"
      @save="saveUser"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseIconButton from '../components/ui/BaseIconButton.vue'
import BasePageHeader from '../components/ui/BasePageHeader.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import UserFormModal from '../components/users/UserFormModal.vue'
import { usersApi } from '../api/users'
import { employeesApi } from '../api/employees'
import { ASSIGNABLE_ROLE_OPTIONS, ROLE_LABELS } from '../constants/roles'
import { useUi } from '../services/ui'

defineOptions({ name: 'UsersPage' })

/**
 * Страница учётных записей пользователей.
 *
 * Здесь super-admin создаёт логины, назначает роли и при необходимости
 * связывает пользователя с сотрудником. Роль определяет, какие разделы и
 * действия будут доступны: например оператор КПП может работать с гостями, HR
 * с сотрудниками, техник с планами и камерами, аналитик с отчётами.
 */
const ui = useUi()
const users = ref([])
const employees = ref([])
const displayDialog = ref(false)
const isEditMode = ref(false)

const roleLabels = ROLE_LABELS
const roleOptions = ASSIGNABLE_ROLE_OPTIONS

const form = ref({
  id: null,
  username: '',
  password: '',
  role: 'checkpoint_operator',
  is_active: true,
  employee_id: null,
})

const availableEmployees = computed(() => {
  const linkedIds = new Set(users.value.filter((user) => user.employee_id && user.id !== form.value.id).map((user) => user.employee_id))
  return employees.value
    .map((employee) => ({
      ...employee,
      full_name: [employee.last_name, employee.first_name, employee.middle_name].filter(Boolean).join(' '),
    }))
    .filter((employee) => !linkedIds.has(employee.id))
    .sort((a, b) => a.full_name.localeCompare(b.full_name, 'ru'))
})

async function loadData() {
  try {
    const [usersRes, employeesRes] = await Promise.all([
      usersApi.getUsers(),
      employeesApi.getEmployees(0, 1000),
    ])
    users.value = usersRes.data
    employees.value = employeesRes.data
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось загрузить пользователей'))
  }
}

function resetForm() {
  form.value = {
    id: null,
    username: '',
    password: '',
    role: 'checkpoint_operator',
    is_active: true,
    employee_id: null,
  }
}

function openCreateDialog() {
  isEditMode.value = false
  resetForm()
  displayDialog.value = true
}

function openEditDialog(user) {
  isEditMode.value = true
  form.value = {
    id: user.id,
    username: user.username,
    password: '',
    role: user.role,
    is_active: user.is_active,
    employee_id: user.employee_id || null,
  }
  displayDialog.value = true
}

function closeDialog() {
  displayDialog.value = false
  resetForm()
}

async function saveUser() {
  if (!form.value.username.trim()) {
    return ui.warn('Введите логин')
  }
  if (!isEditMode.value && !form.value.password) {
    return ui.warn('Введите пароль')
  }

  const payload = {
    username: form.value.username.trim(),
    role: form.value.role,
    is_active: form.value.is_active,
    employee_id: form.value.employee_id,
  }

  if (form.value.password) {
    payload.password = form.value.password
  }

  try {
    if (isEditMode.value) {
      await usersApi.updateUser(form.value.id, payload)
    } else {
      await usersApi.createUser(payload)
    }
    closeDialog()
    await loadData()
    ui.success(isEditMode.value ? 'Пользователь обновлён' : 'Пользователь создан')
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось сохранить пользователя'))
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.page-container { display: flex; flex-direction: column; gap: 1.5rem; }

.table-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; }
.users-table { width: 100%; border-collapse: collapse; }
.users-table th, .users-table td { padding: 1rem 1.25rem; border-bottom: 1px solid #f1f5f9; text-align: left; }
.users-table th { background: #f8fafc; color: #475569; font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.04em; }
.empty-cell { text-align: center; color: #94a3b8; }
</style>
