<template>
  <div class="page-container">
    <div class="header-actions">
      <h1 class="page-title">Сотрудники</h1>
      <button class="btn-primary" @click="openNewDialog">
        <i class="pi pi-plus"></i> Добавить
      </button>
    </div>

    <DataTable
      :value="employees"
      responsiveLayout="scroll"
      class="p-datatable-sm modern-table"
    >
      <Column field="id" header="ID" sortable />
      <Column header="Фамилия">
        <template #body="slotProps">{{ slotProps.data.last_name }}</template>
      </Column>
      <Column header="Имя">
        <template #body="slotProps">{{ slotProps.data.first_name }}</template>
      </Column>
      <Column header="Отчество">
        <template #body="slotProps">{{ slotProps.data.middle_name || '-' }}</template>
      </Column>
      <Column header="Отдел">
        <template #body="slotProps">{{ getDepartmentName(slotProps.data.department_id) }}</template>
      </Column>
      <Column header="Статус">
        <template #body="slotProps">
          <span :class="['status-badge', slotProps.data.is_active ? 'active' : 'inactive']">
            {{ slotProps.data.is_active ? 'Активен' : 'Заблокирован' }}
          </span>
        </template>
      </Column>
      <Column header="Действия">
        <template #body="slotProps">
          <div class="action-buttons">
            <button
              class="btn-icon warning"
              @click="openEditDialog(slotProps.data)"
              title="Редактировать"
            >
              <i class="pi pi-pencil"></i>
            </button>
            <button
              class="btn-icon danger"
              @click="confirmDelete(slotProps.data.id)"
              title="Удалить"
            >
              <i class="pi pi-trash"></i>
            </button>
          </div>
        </template>
      </Column>
    </DataTable>

    <div v-if="displayDialog" class="modal-overlay" @click.self="closeDialog">
      <div class="modal-content">
        <div class="modal-header">
          <h2>{{ isEditMode ? 'Редактировать сотрудника' : 'Новый сотрудник' }}</h2>
          <button class="btn-icon close-btn" @click="closeDialog">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div v-if="isDialogLoading" class="dialog-loading">
          Загрузка...
        </div>

        <template v-else>
          <div class="form-grid">
            <div class="form-group">
              <label>Фамилия <span class="required">*</span></label>
              <input
                v-model="employeeForm.last_name"
                type="text"
                class="form-input"
                placeholder="Иванов"
              />
            </div>

            <div class="form-group">
              <label>Имя <span class="required">*</span></label>
              <input
                v-model="employeeForm.first_name"
                type="text"
                class="form-input"
                placeholder="Иван"
              />
            </div>

            <div class="form-group">
              <label>Отчество</label>
              <input
                v-model="employeeForm.middle_name"
                type="text"
                class="form-input"
                placeholder="Иванович"
              />
            </div>

            <div class="form-group">
              <label>Отдел <span class="required">*</span></label>
              <select v-model="employeeForm.department_id" class="form-input">
                <option value="" disabled>Выберите отдел...</option>
                <option
                  v-for="dept in departments"
                  :key="dept.id"
                  :value="dept.id"
                >
                  {{ dept.name }}
                </option>
              </select>
            </div>
          </div>

          <div v-if="isEditMode" class="form-group checkbox-group">
            <input id="isActive" v-model="employeeForm.is_active" type="checkbox" />
            <label for="isActive">Сотрудник активен (имеет доступ)</label>
          </div>

          <div class="photo-upload-section">
            <label>Фотографии лица <span class="required">*</span></label>
            <p class="photo-hint">
              Клик по карточке делает фото основным. Крестик удаляет фото.
            </p>

            <div class="gallery-container">
              <div
                v-for="photo in existingPhotos"
                :key="`existing-${photo.id}`"
                :class="['photo-card', { 'is-primary': primaryType === 'existing' && primaryRef === photo.id }]"
                @click="setPrimary('existing', photo.id)"
              >
                <img
                  :src="getPhotoUrl(photo.id)"
                  alt="Фото сотрудника"
                  class="photo-thumbnail"
                  @error="handleImageError"
                />
                <div
                  v-if="primaryType === 'existing' && primaryRef === photo.id"
                  class="primary-badge"
                >
                  <i class="pi pi-star-fill"></i> Главная
                </div>
                <button class="remove-photo-btn" @click.stop="removeExistingPhoto(photo.id)">
                  <i class="pi pi-times"></i>
                </button>
              </div>

              <div
                v-for="(preview, index) in newPreviews"
                :key="`new-${index}`"
                :class="['photo-card', { 'is-primary': primaryType === 'new' && primaryRef === index }]"
                @click="setPrimary('new', index)"
              >
                <img :src="preview" alt="Новое фото" class="photo-thumbnail" />
                <div class="new-badge">Новое</div>
                <div
                  v-if="primaryType === 'new' && primaryRef === index"
                  class="primary-badge"
                >
                  <i class="pi pi-star-fill"></i> Главная
                </div>
                <button class="remove-photo-btn" @click.stop="removeNewPhoto(index)">
                  <i class="pi pi-times"></i>
                </button>
              </div>

              <label class="upload-trigger">
                <input
                  type="file"
                  multiple
                  accept="image/*"
                  class="hidden-input"
                  @change="onFilesSelect"
                />
                <i class="pi pi-camera"></i>
                <span>Добавить</span>
              </label>
            </div>
          </div>

          <div class="modal-actions">
            <button class="btn-text" :disabled="isSaving" @click="closeDialog">
              Отмена
            </button>
            <button class="btn-primary" :disabled="isSaving" @click="saveEmployee">
              <i class="pi pi-check"></i>
              {{ isSaving ? 'Сохранение...' : 'Сохранить' }}
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { employeesApi } from '../api/employees'
import { departmentsApi } from '../api/departments'

const employees = ref([])
const departments = ref([])

const displayDialog = ref(false)
const isEditMode = ref(false)
const currentEmployeeId = ref(null)
const isDialogLoading = ref(false)
const isSaving = ref(false)

const employeeForm = ref({
  last_name: '',
  first_name: '',
  middle_name: '',
  department_id: '',
  is_active: true
})

const existingPhotos = ref([])
const deletedPhotoIds = ref([])
const newFiles = ref([])
const newPreviews = ref([])

const primaryType = ref(null) // 'existing' | 'new' | null
const primaryRef = ref(null)

const FALLBACK_IMAGE =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
      <rect width="100%" height="100%" fill="#e2e8f0"/>
      <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#64748b" font-size="12">
        Нет фото
      </text>
    </svg>
  `)

function resetForm() {
  employeeForm.value = {
    last_name: '',
    first_name: '',
    middle_name: '',
    department_id: '',
    is_active: true
  }
}

function resetPhotosState() {
  existingPhotos.value = []
  deletedPhotoIds.value = []
  newFiles.value = []

  newPreviews.value.forEach((url) => URL.revokeObjectURL(url))
  newPreviews.value = []

  primaryType.value = null
  primaryRef.value = null
}

function closeDialog() {
  displayDialog.value = false
  isDialogLoading.value = false
  isSaving.value = false
  currentEmployeeId.value = null
  isEditMode.value = false
  resetForm()
  resetPhotosState()
}

function getDepartmentName(departmentId) {
  const department = departments.value.find((item) => item.id === departmentId)
  return department ? department.name : '-'
}

function getPhotoUrl(sampleId) {
  return employeesApi.getFaceSamplePhotoUrl(sampleId)
}

function handleImageError(event) {
  event.target.src = FALLBACK_IMAGE
}

async function loadData() {
  try {
    const [empRes, depRes] = await Promise.all([
      employeesApi.getEmployees(),
      departmentsApi.getDepartments()
    ])

    employees.value = empRes.data
    departments.value = depRes.data
  } catch (error) {
    alert('Не удалось загрузить сотрудников и отделы')
  }
}

function openNewDialog() {
  closeDialog()
  isEditMode.value = false
  displayDialog.value = true
}

async function openEditDialog(employee) {
  closeDialog()
  isEditMode.value = true
  currentEmployeeId.value = employee.id
  displayDialog.value = true
  isDialogLoading.value = true

  try {
    const response = await employeesApi.getEmployee(employee.id)
    const fullEmployee = response.data

    employeeForm.value = {
      last_name: fullEmployee.last_name ?? '',
      first_name: fullEmployee.first_name ?? '',
      middle_name: fullEmployee.middle_name ?? '',
      department_id: fullEmployee.department_id ?? '',
      is_active: Boolean(fullEmployee.is_active)
    }

    existingPhotos.value = (fullEmployee.face_samples || []).map((sample) => ({
      id: sample.id,
      is_primary: Boolean(sample.is_primary)
    }))

    const primaryExisting = existingPhotos.value.find((item) => item.is_primary)

    if (primaryExisting) {
      primaryType.value = 'existing'
      primaryRef.value = primaryExisting.id
    } else if (existingPhotos.value.length > 0) {
      primaryType.value = 'existing'
      primaryRef.value = existingPhotos.value[0].id
    } else {
      primaryType.value = null
      primaryRef.value = null
    }
  } catch (error) {
    alert(error.response?.data?.detail || 'Не удалось загрузить карточку сотрудника')
    closeDialog()
  } finally {
    isDialogLoading.value = false
  }
}

function onFilesSelect(event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return

  files.forEach((file) => {
    newFiles.value.push(file)
    newPreviews.value.push(URL.createObjectURL(file))
  })

  if (primaryType.value === null && newFiles.value.length > 0) {
    primaryType.value = 'new'
    primaryRef.value = 0
  }

  event.target.value = ''
}

function setPrimary(type, refValue) {
  primaryType.value = type
  primaryRef.value = refValue
}

function fallbackPrimary() {
  if (existingPhotos.value.length > 0) {
    primaryType.value = 'existing'
    primaryRef.value = existingPhotos.value[0].id
    return
  }

  if (newFiles.value.length > 0) {
    primaryType.value = 'new'
    primaryRef.value = 0
    return
  }

  primaryType.value = null
  primaryRef.value = null
}

function removeExistingPhoto(id) {
  if (!deletedPhotoIds.value.includes(id)) {
    deletedPhotoIds.value.push(id)
  }

  existingPhotos.value = existingPhotos.value.filter((photo) => photo.id !== id)

  if (primaryType.value === 'existing' && primaryRef.value === id) {
    fallbackPrimary()
  }
}

function removeNewPhoto(index) {
  URL.revokeObjectURL(newPreviews.value[index])

  newFiles.value.splice(index, 1)
  newPreviews.value.splice(index, 1)

  if (primaryType.value === 'new' && primaryRef.value === index) {
    fallbackPrimary()
    return
  }

  if (primaryType.value === 'new' && primaryRef.value > index) {
    primaryRef.value -= 1
  }
}

async function saveEmployee() {
  const lastName = employeeForm.value.last_name.trim()
  const firstName = employeeForm.value.first_name.trim()
  const middleName = employeeForm.value.middle_name.trim()
  const departmentId = employeeForm.value.department_id

  if (!lastName || !firstName || !departmentId) {
    alert('Заполните обязательные поля')
    return
  }

  const totalPhotos = existingPhotos.value.length + newFiles.value.length

  if (!isEditMode.value && totalPhotos === 0) {
    alert('Для нового сотрудника нужно добавить хотя бы одно фото')
    return
  }

  if (isEditMode.value && employeeForm.value.is_active && totalPhotos === 0) {
    alert('У активного сотрудника должна быть хотя бы одна фотография')
    return
  }

  const formData = new FormData()
  formData.append('last_name', lastName)
  formData.append('first_name', firstName)
  formData.append('department_id', String(departmentId))

  if (middleName) {
    formData.append('middle_name', middleName)
  }

  newFiles.value.forEach((file) => {
    formData.append('photos', file)
  })

  isSaving.value = true

  try {
    if (isEditMode.value) {
      formData.append('is_active', String(employeeForm.value.is_active))
      formData.append('delete_sample_ids', JSON.stringify(deletedPhotoIds.value))

      if (primaryType.value !== null && primaryRef.value !== null) {
        formData.append('primary_photo', `${primaryType.value}:${primaryRef.value}`)
      }

      await employeesApi.updateEmployee(currentEmployeeId.value, formData)
    } else {
      const primaryIndex =
        primaryType.value === 'new' && primaryRef.value !== null ? primaryRef.value : 0

      formData.append('primary_index', String(primaryIndex))
      await employeesApi.createEmployee(formData)
    }

    closeDialog()
    await loadData()
  } catch (error) {
    alert(error.response?.data?.detail || 'Ошибка при сохранении сотрудника')
  } finally {
    isSaving.value = false
  }
}

async function confirmDelete(id) {
  const ok = window.confirm('Точно удалить сотрудника?')
  if (!ok) return

  try {
    await employeesApi.deleteEmployee(id)
    await loadData()
  } catch (error) {
    alert(error.response?.data?.detail || 'Не удалось удалить сотрудника')
  }
}

onMounted(async () => {
  await loadData()
})
</script>

<style scoped>
.page-container { background: #ffffff; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05); }
.header-actions { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
.page-title { font-size: 1.5rem; font-weight: 600; color: #1e293b; }
.btn-primary { background-color: #10b981; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 0.5rem; font-weight: 600; transition: background-color 0.2s; }
.btn-primary:hover { background-color: #059669; }
.btn-primary:disabled { opacity: 0.7; cursor: not-allowed; }
.btn-text { background: transparent; border: none; color: #64748b; cursor: pointer; padding: 0.6rem 1.2rem; font-weight: 600; }
.btn-text:hover { color: #334155; }
.btn-text:disabled { opacity: 0.7; cursor: not-allowed; }
.action-buttons { display: flex; gap: 0.5rem; }
.btn-icon { background: transparent; border: none; cursor: pointer; padding: 0.5rem; border-radius: 6px; transition: background-color 0.2s; }
.btn-icon.danger { color: #ef4444; }
.btn-icon.danger:hover { background-color: #fee2e2; }
.btn-icon.warning { color: #f59e0b; }
.btn-icon.warning:hover { background-color: #fef3c7; }
.close-btn { color: #64748b; font-size: 1.2rem; }
.close-btn:hover { background-color: #f1f5f9; color: #0f172a; }
.status-badge { padding: 0.3rem 0.6rem; border-radius: 6px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; }
.status-badge.active { background: #dcfce7; color: #166534; }
.status-badge.inactive { background: #f1f5f9; color: #475569; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: white; padding: 2.5rem; border-radius: 16px; width: 100%; max-width: 650px; max-height: 90vh; overflow-y: auto; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1); }
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
.modal-header h2 { font-size: 1.5rem; color: #0f172a; }
.dialog-loading { padding: 2rem 0; text-align: center; color: #64748b; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }
.form-group label { display: block; margin-bottom: 0.5rem; font-size: 0.875rem; font-weight: 500; color: #475569; }
.required { color: #ef4444; }
.form-input { width: 100%; padding: 0.75rem 1rem; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 0.95rem; color: #1e293b; background-color: #f8fafc; }
.form-input:focus { outline: none; border-color: #10b981; background-color: #ffffff; box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1); }
.checkbox-group { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 2rem; }
.checkbox-group input { width: 1.25rem; height: 1.25rem; accent-color: #10b981; }

.photo-upload-section { margin-bottom: 2rem; }
.photo-upload-section label { display: block; font-size: 0.875rem; font-weight: 500; color: #475569; margin-bottom: 0.25rem; }
.photo-hint { font-size: 0.8rem; color: #94a3b8; margin-bottom: 1rem; }
.gallery-container { display: flex; flex-wrap: wrap; gap: 1rem; }

.photo-card { position: relative; width: 100px; height: 100px; border-radius: 12px; overflow: hidden; cursor: pointer; border: 2px solid transparent; transition: all 0.2s; }
.photo-card:hover { transform: translateY(-2px); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
.photo-card.is-primary { border-color: #10b981; }
.photo-thumbnail { width: 100%; height: 100%; object-fit: cover; }

.primary-badge { position: absolute; bottom: 0; left: 0; right: 0; background: rgba(16, 185, 129, 0.9); color: white; font-size: 0.65rem; font-weight: 600; text-align: center; padding: 0.25rem 0; }
.new-badge { position: absolute; top: 0; left: 0; background: #3b82f6; color: white; font-size: 0.6rem; font-weight: bold; padding: 0.1rem 0.4rem; border-bottom-right-radius: 6px; }

.remove-photo-btn { position: absolute; top: 4px; right: 4px; background: rgba(15, 23, 42, 0.6); color: white; border: none; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 0.7rem; }
.remove-photo-btn:hover { background: #ef4444; }

.hidden-input { display: none; }
.upload-trigger { width: 100px; height: 100px; border: 2px dashed #cbd5e1; border-radius: 12px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #64748b; cursor: pointer; background-color: #f8fafc; }
.upload-trigger:hover { border-color: #10b981; color: #10b981; background-color: #ecfdf5; }
.upload-trigger i { font-size: 1.5rem; margin-bottom: 0.5rem; }

.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; padding-top: 1.5rem; border-top: 1px solid #e2e8f0; }
</style>