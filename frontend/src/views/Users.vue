<template>
  <div class="page-container">
    <div class="header-actions">
      <div>
        <h1 class="page-title">Пользователи системы</h1>
        <p class="page-subtitle">Создание учетных записей для super admin и операторов КПП.</p>
      </div>
      <button class="btn-primary" @click="openCreateDialog">
        <i class="pi pi-plus"></i> Новый пользователь
      </button>
    </div>

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
              <span class="role-badge">{{ roleLabels[user.role] || user.role }}</span>
            </td>
            <td>{{ user.employee_name || 'Не привязан' }}</td>
            <td>
              <span class="status-badge" :class="user.is_active ? 'active' : 'blocked'">
                {{ user.is_active ? 'Активен' : 'Отключен' }}
              </span>
            </td>
            <td>
              <button class="btn-icon warning" @click="openEditDialog(user)" title="Редактировать">
                <i class="pi pi-pencil"></i>
              </button>
            </td>
          </tr>
          <tr v-if="users.length === 0">
            <td colspan="5" class="empty-cell">Пользователи пока не созданы.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="displayDialog" class="modal-overlay" @click.self="closeDialog">
      <div class="modal-content">
        <div class="modal-header">
          <h2>{{ isEditMode ? 'Редактировать пользователя' : 'Новый пользователь' }}</h2>
          <button class="btn-icon close-btn" @click="closeDialog">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="form-grid">
          <div class="form-group">
            <label>Логин <span class="required">*</span></label>
            <input v-model="form.username" type="text" class="form-input" />
          </div>

          <div class="form-group">
            <label>Роль <span class="required">*</span></label>
            <select v-model="form.role" class="form-input">
              <option v-for="option in roleOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>

          <div class="form-group full-width">
            <label>Привязать к сотруднику</label>
            <select v-model="linkedEmployeeValue" class="form-input">
              <option value="">Не привязывать</option>
              <option v-for="employee in availableEmployees" :key="employee.id" :value="String(employee.id)">
                {{ employee.full_name }}
              </option>
            </select>
          </div>

          <div class="form-group full-width">
            <label>
              {{ isEditMode ? 'Новый пароль' : 'Пароль' }}
              <span v-if="!isEditMode" class="required">*</span>
            </label>
            <input v-model="form.password" type="password" class="form-input" />
            <small class="field-hint">
              {{ isEditMode ? 'Оставь пустым, если пароль менять не нужно.' : 'Минимум 6 символов.' }}
            </small>
          </div>
        </div>

        <div class="form-group checkbox-group">
          <input id="userActive" v-model="form.is_active" type="checkbox" />
          <label for="userActive">Учетная запись активна</label>
        </div>

        <div class="modal-actions">
          <button class="btn-text" @click="closeDialog">Отмена</button>
          <button class="btn-primary" @click="saveUser">Сохранить</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { usersApi } from '../api/users'
import { employeesApi } from '../api/employees'

const users = ref([])
const employees = ref([])
const displayDialog = ref(false)
const isEditMode = ref(false)


const roleLabels = {
  super_admin: 'Super Admin',
  checkpoint_operator: 'Оператор КПП',
}

const roleOptions = [
  { value: 'super_admin', label: 'Super Admin' },
  { value: 'checkpoint_operator', label: 'Оператор КПП' },
]

const form = ref({
  id: null,
  username: '',
  password: '',
  role: 'checkpoint_operator',
  is_active: true,
  employee_id: null,
})

const linkedEmployeeValue = computed({
  get: () => (form.value.employee_id ? String(form.value.employee_id) : ''),
  set: (value) => {
    form.value.employee_id = value ? Number(value) : null
  },
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
    alert(error.response?.data?.detail || 'Не удалось загрузить пользователей')
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
    return alert('Введите логин')
  }
  if (!isEditMode.value && !form.value.password) {
    return alert('Введите пароль')
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
  } catch (error) {
    alert(error.response?.data?.detail || 'Не удалось сохранить пользователя')
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.page-container { display: flex; flex-direction: column; gap: 1.5rem; }
.header-actions { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-size: 1.75rem; font-weight: 700; color: #0f172a; margin: 0; }
.page-subtitle { margin-top: 0.35rem; color: #64748b; font-size: 0.95rem; }

.table-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; }
.users-table { width: 100%; border-collapse: collapse; }
.users-table th, .users-table td { padding: 1rem 1.25rem; border-bottom: 1px solid #f1f5f9; text-align: left; }
.users-table th { background: #f8fafc; color: #475569; font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.04em; }
.empty-cell { text-align: center; color: #94a3b8; }

.role-badge { display: inline-flex; align-items: center; padding: 0.35rem 0.65rem; border-radius: 999px; background: #eff6ff; color: #1d4ed8; font-size: 0.8rem; font-weight: 600; }
.status-badge { padding: 0.35rem 0.75rem; border-radius: 999px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.04em; }
.status-badge.active { background: #dcfce7; color: #166534; }
.status-badge.blocked { background: #fee2e2; color: #991b1b; }

.btn-primary, .btn-text { border: none; padding: 0.7rem 1.2rem; border-radius: 10px; cursor: pointer; display: inline-flex; align-items: center; gap: 0.5rem; font-weight: 600; }
.btn-primary { background: #2563eb; color: white; }
.btn-text { background: transparent; color: #64748b; }
.btn-icon { background: transparent; border: none; cursor: pointer; width: 34px; height: 34px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; }
.btn-icon.warning { color: #f59e0b; }
.btn-icon.warning:hover { background: #fef3c7; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.6); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 1rem; }
.modal-content { width: min(560px, calc(100vw - 2rem)); background: #ffffff; border-radius: 20px; padding: 1.5rem; }
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.form-group { display: flex; flex-direction: column; gap: 0.45rem; }
.form-group.full-width { grid-column: 1 / -1; }
.form-input { width: 100%; border: 1px solid #cbd5e1; border-radius: 10px; padding: 0.75rem 0.9rem; background: #f8fafc; }
.field-hint { color: #64748b; font-size: 0.8rem; }
.required { color: #ef4444; }
.checkbox-group { margin-top: 1rem; display: flex; align-items: center; gap: 0.6rem; }
.modal-actions { margin-top: 1.5rem; display: flex; justify-content: flex-end; gap: 0.75rem; }
.close-btn { color: #64748b; }
</style>
