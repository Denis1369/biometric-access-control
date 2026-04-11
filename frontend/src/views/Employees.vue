<template>
  <div class="page-container">
    <div class="header-actions">
      <div>
        <h1 class="page-title">Сотрудники</h1>
        <p class="page-subtitle">Управление персоналом, доступом и биометрией.</p>
      </div>
      <button class="btn-primary" @click="openNewDialog">
        <i class="pi pi-plus"></i> Добавить
      </button>
    </div>

    <div class="filters-bar">
      <div class="search-box">
        <i class="pi pi-search"></i>
        <input type="text" v-model="searchQuery" placeholder="Поиск по ФИО или должности..." />
      </div>

      <select v-model="selectedDept" class="filter-select">
        <option value="all">Все отделы</option>
        <option v-for="dept in departments" :key="dept.id" :value="String(dept.id)">{{ dept.name }}</option>
      </select>

      <select v-model="selectedStatus" class="filter-select">
        <option value="all">Все статусы</option>
        <option value="active">Только активные</option>
        <option value="blocked">Заблокированные</option>
      </select>
    </div>

    <div class="cards-grid">
      <div v-for="emp in filteredEmployees" :key="emp.id" class="employee-card">
        <div class="card-header">
          <div class="status-badge" :class="emp.is_active ? 'active' : 'blocked'">
            {{ emp.is_active ? 'АКТИВЕН' : 'ЗАБЛОКИРОВАН' }}
          </div>
          <div class="card-actions">
            <button class="btn-icon" @click="openEditDialog(emp)" title="Редактировать">
              <i class="pi pi-pencil"></i>
            </button>
          </div>
        </div>

        <div class="card-body">
          <div class="avatar-container">
            <img v-if="emp.primary_sample_id" :src="employeesApi.getFaceSamplePhotoUrl(emp.primary_sample_id)" class="avatar-img" />
            <div v-else class="avatar-placeholder">{{ getInitials(emp.last_name, emp.first_name) }}</div>
          </div>

          <h3 class="emp-name">{{ emp.last_name }} {{ emp.first_name }}</h3>
          <p class="emp-middle-name">{{ emp.middle_name || ' ' }}</p>

          <div v-if="emp.position" class="emp-position"><i class="pi pi-id-card"></i> {{ emp.position }}</div>
          <div class="emp-dept"><i class="pi pi-briefcase"></i> {{ getDeptName(emp.department_id) }}</div>
        </div>
      </div>

      <div v-if="filteredEmployees.length === 0" class="empty-state">
        <i class="pi pi-users empty-icon"></i>
        <h3>Сотрудники не найдены</h3>
        <p>По вашему запросу нет совпадений.</p>
      </div>
    </div>

    <div v-if="displayDialog" class="modal-overlay" @click.self="closeDialog">
      <div class="modal-content">
        <div class="modal-header">
          <h2>{{ isEditMode ? 'Редактировать сотрудника' : 'Новый сотрудник' }}</h2>
          <button class="btn-icon close-btn" @click="closeDialog"><i class="pi pi-times"></i></button>
        </div>

        <div class="photos-section">
          <label class="section-label">Фотографии лица <span class="required">*</span></label>
          <div class="photos-gallery">
            <div v-for="photo in existingPhotos" :key="'ex' + photo.id" class="photo-item" :class="{ 'is-primary': primaryPhoto.type === 'existing' && primaryPhoto.idOrIndex === photo.id }">
              <img :src="photo.url" />
              <div class="photo-actions"><button @click.prevent="setPrimary('existing', photo.id)"><i class="pi pi-star-fill"></i></button></div>
              <div class="primary-badge" v-if="primaryPhoto.type === 'existing' && primaryPhoto.idOrIndex === photo.id">Главная</div>
            </div>
            <div v-for="(photo, index) in newPhotos" :key="'new' + index" class="photo-item" :class="{ 'is-primary': primaryPhoto.type === 'new' && primaryPhoto.idOrIndex === index }">
              <img :src="photo.url" />
              <div class="photo-actions">
                <button @click.prevent="setPrimary('new', index)"><i class="pi pi-star-fill"></i></button>
                <button class="danger" @click.prevent="removeNewPhoto(index)"><i class="pi pi-trash"></i></button>
              </div>
              <div class="primary-badge" v-if="primaryPhoto.type === 'new' && primaryPhoto.idOrIndex === index">Новая главная</div>
            </div>
            <div class="photo-item add-new" @click="triggerUpload">
              <i class="pi pi-camera"></i><span>Добавить</span>
            </div>
            <input type="file" multiple accept="image/*" ref="fileInput" class="hidden-input" @change="onFileSelected" />
          </div>
        </div>

        <div class="form-grid">
          <div class="form-group">
            <label>Фамилия <span class="required">*</span></label>
            <input v-model="empForm.last_name" type="text" class="form-input" />
          </div>
          <div class="form-group">
            <label>Имя <span class="required">*</span></label>
            <input v-model="empForm.first_name" type="text" class="form-input" />
          </div>
          <div class="form-group">
            <label>Отчество</label>
            <input v-model="empForm.middle_name" type="text" class="form-input" />
          </div>

          <div class="form-group">
            <label>Отдел <span class="required">*</span></label>
            <select v-model="empForm.department_id" class="form-input">
              <option value="" disabled>Выберите отдел...</option>
              <option v-for="dept in departments" :key="dept.id" :value="String(dept.id)">{{ dept.name }}</option>
            </select>
          </div>

          <div class="form-group position-group full-width">
            <div class="label-row">
              <label>Должность</label>
              <span class="hint" v-if="!empForm.department_id">Сначала выберите отдел</span>
            </div>
            <select v-model="empForm.position" class="form-input" :disabled="!empForm.department_id">
              <option value="">Не выбрана</option>
              <option v-for="position in activePositions" :key="position.id" :value="position.name">
                {{ position.name }}
              </option>
            </select>
          </div>
        </div>

        <div class="form-group checkbox-group" v-if="isEditMode">
          <input type="checkbox" id="isActive" v-model="empForm.is_active" />
          <label for="isActive">Доступ разрешен (Активен)</label>
        </div>

        <div class="modal-actions">
          <button class="btn-text" @click="closeDialog">Отмена</button>
          <button class="btn-primary" @click="saveEmployee">Сохранить</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { employeesApi } from '../api/employees'
import { departmentsApi } from '../api/departments'
import { jobPositionsApi } from '../api/jobPositions'

defineOptions({ name: 'EmployeesPage' })

const employees = ref([])
const departments = ref([])
const allPositions = ref([])

const searchQuery = ref('')
const selectedDept = ref('all')
const selectedStatus = ref('all')

const displayDialog = ref(false)
const isEditMode = ref(false)
const fileInput = ref(null)
const existingPhotos = ref([])
const newPhotos = ref([])
const removedPhotoIds = ref([])
const primaryPhoto = ref({ type: null, idOrIndex: null })

const empForm = ref({ id: null, last_name: '', first_name: '', middle_name: '', position: '', department_id: '', is_active: true })

const loadData = async () => {
  try {
    const [empRes, deptRes, positionRes] = await Promise.all([
      employeesApi.getEmployees(0, 1000),
      departmentsApi.getDepartments(),
      jobPositionsApi.getJobPositions(true)
    ])
    employees.value = empRes.data
    departments.value = deptRes.data
    allPositions.value = positionRes.data
  } catch {
    employees.value = []
    departments.value = []
    allPositions.value = []
  }
}

// ДИНАМИЧЕСКИЙ СПИСОК ДОЛЖНОСТЕЙ В ЗАВИСИМОСТИ ОТ ОТДЕЛА
const activePositions = computed(() => {
  if (!empForm.value.department_id) return []
  return allPositions.value.filter(p => p.is_active && String(p.department_id) === String(empForm.value.department_id))
})

// СБРОС ДОЛЖНОСТИ ПРИ СМЕНЕ ОТДЕЛА
watch(() => empForm.value.department_id, (newDeptId) => {
  if (!newDeptId) return
  // Если текущая выбранная должность не принадлежит новому отделу, сбрасываем её
  const isValid = activePositions.value.some(p => p.name === empForm.value.position)
  if (!isValid) {
    empForm.value.position = ''
  }
})

const filteredEmployees = computed(() => {
  return employees.value.filter(emp => {
    const haystack = `${emp.last_name} ${emp.first_name} ${emp.middle_name || ''} ${emp.position || ''}`.toLowerCase()
    const matchesSearch = haystack.includes(searchQuery.value.toLowerCase())
    const matchesDept = selectedDept.value === 'all' || String(emp.department_id) === String(selectedDept.value)
    const matchesStatus = selectedStatus.value === 'all' || (selectedStatus.value === 'active' && emp.is_active) || (selectedStatus.value === 'blocked' && !emp.is_active)
    return matchesSearch && matchesDept && matchesStatus
  })
})

const getDeptName = id => { const d = departments.value.find(d => String(d.id) === String(id)); return d ? d.name : 'Не указан' }
const getInitials = (last, first) => `${(last || '').charAt(0)}${(first || '').charAt(0)}`.toUpperCase()
const triggerUpload = () => { if (fileInput.value) fileInput.value.click() }
const setPrimary = (type, idOrIndex) => { primaryPhoto.value = { type, idOrIndex } }
const autoSetPrimary = () => { if (existingPhotos.value.length > 0) setPrimary('existing', existingPhotos.value[0].id); else if (newPhotos.value.length > 0) setPrimary('new', 0); else setPrimary(null, null) }
const onFileSelected = e => { Array.from(e.target.files).forEach(f => newPhotos.value.push({ file: f, url: URL.createObjectURL(f) })); if (!primaryPhoto.value.type && newPhotos.value.length > 0 && existingPhotos.value.length === 0) setPrimary('new', 0); e.target.value = '' }
const removeNewPhoto = i => { URL.revokeObjectURL(newPhotos.value[i].url); newPhotos.value.splice(i, 1); if (primaryPhoto.value.type === 'new' && primaryPhoto.value.idOrIndex === i) autoSetPrimary(); else if (primaryPhoto.value.type === 'new' && primaryPhoto.value.idOrIndex > i) primaryPhoto.value.idOrIndex -= 1 }

const openNewDialog = () => {
  isEditMode.value = false; empForm.value = { id: null, last_name: '', first_name: '', middle_name: '', position: '', department_id: '', is_active: true }
  existingPhotos.value = []; newPhotos.value.forEach(p => URL.revokeObjectURL(p.url)); newPhotos.value = []; removedPhotoIds.value = []; primaryPhoto.value = { type: null, idOrIndex: null }
  displayDialog.value = true
}

const openEditDialog = async emp => {
  isEditMode.value = true; empForm.value = { ...emp, position: emp.position || '', department_id: String(emp.department_id) }
  newPhotos.value.forEach(p => URL.revokeObjectURL(p.url)); newPhotos.value = []; removedPhotoIds.value = []
  try {
    const res = await employeesApi.getEmployee(emp.id)
    existingPhotos.value = res.data.face_samples.map(s => ({ id: s.id, url: employeesApi.getFaceSamplePhotoUrl(s.id), is_primary: s.is_primary }))
    const primary = res.data.face_samples.find(s => s.is_primary); if (primary) setPrimary('existing', primary.id); else autoSetPrimary()
    displayDialog.value = true
  } catch { alert('Ошибка загрузки') }
}

const closeDialog = () => { displayDialog.value = false; newPhotos.value.forEach(p => URL.revokeObjectURL(p.url)); newPhotos.value = [] }

const saveEmployee = async () => {
  if (!empForm.value.last_name || !empForm.value.first_name || !empForm.value.department_id) return alert('Заполните обязательные поля')
  if (existingPhotos.value.length === 0 && newPhotos.value.length === 0) return alert('Нужно фото')
  try {
    const formData = new FormData()
    formData.append('last_name', empForm.value.last_name)
    formData.append('first_name', empForm.value.first_name)
    if (empForm.value.middle_name) formData.append('middle_name', empForm.value.middle_name)
    formData.append('position', empForm.value.position || '')
    formData.append('department_id', empForm.value.department_id)
    newPhotos.value.forEach(p => formData.append('photos', p.file))

    if (isEditMode.value) {
      formData.append('is_active', empForm.value.is_active)
      if (removedPhotoIds.value.length > 0) formData.append('delete_sample_ids', JSON.stringify(removedPhotoIds.value))
      if (primaryPhoto.value.type === 'existing') formData.append('primary_photo', `existing:${primaryPhoto.value.idOrIndex}`)
      else if (primaryPhoto.value.type === 'new') formData.append('primary_photo', `new:${primaryPhoto.value.idOrIndex}`)
      await employeesApi.updateEmployee(empForm.value.id, formData)
    } else {
      formData.append('primary_index', primaryPhoto.value.type === 'new' ? primaryPhoto.value.idOrIndex : 0)
      await employeesApi.createEmployee(formData)
    }
    closeDialog(); await loadData()
  } catch (error) { alert(error.response?.data?.detail || 'Ошибка') }
}

onMounted(() => { loadData() })
</script>

<style scoped>
.page-container { background: transparent; height: 100%; display: flex; flex-direction: column; gap: 1.5rem; }
.header-actions { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { font-size: 1.75rem; font-weight: 700; color: #0f172a; margin: 0; }
.page-subtitle { margin: 0.35rem 0 0; color: #64748b; font-size: 0.95rem; }

.filters-bar { display: flex; gap: 1rem; flex-wrap: wrap; background: #ffffff; padding: 1rem; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.search-box { position: relative; flex: 1; min-width: 250px; }
.search-box i { position: absolute; left: 1rem; top: 50%; transform: translateY(-50%); color: #94a3b8; }
.search-box input { width: 100%; padding: 0.75rem 1rem 0.75rem 2.5rem; border-radius: 8px; border: 1px solid #cbd5e1; background: #f8fafc; font-size: 0.95rem; outline: none; transition: 0.2s; }
.search-box input:focus { border-color: #3b82f6; background: #ffffff; }
.filter-select { padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid #cbd5e1; background: #f8fafc; color: #334155; font-size: 0.95rem; outline: none; min-width: 180px; cursor: pointer; }

.cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.5rem; }
.employee-card { background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; padding: 1.5rem; transition: transform 0.2s, box-shadow 0.2s; position: relative; display: flex; flex-direction: column; }
.employee-card:hover { transform: translateY(-3px); box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08); }

.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem; }
.status-badge { padding: 0.35rem 0.75rem; border-radius: 999px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em; }
.status-badge.active { background: #dcfce7; color: #166534; }
.status-badge.blocked { background: #fee2e2; color: #991b1b; }
.card-actions { display: flex; gap: 0.25rem; }

.card-body { display: flex; flex-direction: column; align-items: center; text-align: center; }
.avatar-container { margin-bottom: 1rem; }
.avatar-placeholder { width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(135deg, #3b82f6, #8b5cf6); color: white; display: flex; align-items: center; justify-content: center; font-size: 1.75rem; font-weight: 700; letter-spacing: 2px; }
.avatar-img { width: 80px; height: 80px; border-radius: 50%; object-fit: cover; }

.emp-name { margin: 0 0 0.25rem 0; color: #0f172a; font-size: 1.15rem; font-weight: 700; }
.emp-middle-name { margin: 0 0 0.75rem 0; color: #64748b; font-size: 0.9rem; min-height: 1.2rem; }
.emp-position { background: #eff6ff; color: #1d4ed8; padding: 0.45rem 0.75rem; border-radius: 8px; font-size: 0.85rem; font-weight: 600; display: inline-flex; align-items: center; gap: 0.5rem; width: 100%; justify-content: center; margin-bottom: 0.5rem; }
.emp-dept { background: #f1f5f9; color: #475569; padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.85rem; font-weight: 600; display: inline-flex; align-items: center; gap: 0.5rem; width: 100%; justify-content: center; }

.empty-state { grid-column: 1 / -1; display: flex; flex-direction: column; align-items: center; padding: 4rem 2rem; color: #94a3b8; background: #ffffff; border-radius: 16px; border: 1px dashed #cbd5e1; }
.empty-icon { font-size: 3rem; margin-bottom: 1rem; color: #cbd5e1; }

.photos-section { margin-bottom: 1.5rem; }
.section-label { display: block; font-size: 0.9rem; font-weight: 600; color: #475569; margin-bottom: 0.75rem; }
.photos-gallery { display: flex; gap: 1rem; flex-wrap: wrap; }
.photo-item { position: relative; width: 100px; height: 100px; border-radius: 12px; overflow: hidden; border: 2px solid transparent; }
.photo-item.is-primary { border-color: #10b981; }
.photo-item img { width: 100%; height: 100%; object-fit: cover; }
.photo-item.add-new { background: #f8fafc; border: 2px dashed #cbd5e1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #64748b; cursor: pointer; }
.photo-item.add-new i { font-size: 1.5rem; margin-bottom: 0.25rem; }
.photo-item.add-new span { font-size: 0.75rem; font-weight: 600; }
.photo-actions { position: absolute; inset: 0; background: rgba(15,23,42,0.6); display: flex; align-items: center; justify-content: center; gap: 0.5rem; opacity: 0; transition: 0.2s; }
.photo-item:hover .photo-actions { opacity: 1; }
.photo-actions button { background: white; border: none; width: 30px; height: 30px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; color: #475569; transition: 0.2s; }
.photo-actions button.danger { color: #ef4444; }
.primary-badge { position: absolute; bottom: 0; left: 0; right: 0; background: #10b981; color: white; font-size: 0.7rem; font-weight: 700; text-align: center; padding: 0.2rem; }
.hidden-input { display: none; }

.btn-primary, .btn-text { border: none; padding: 0.65rem 1.2rem; border-radius: 8px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 0.5rem; transition: 0.2s; }
.btn-primary { background: #3b82f6; color: white; }
.btn-text { background: transparent; color: #64748b; }
.btn-icon { background: transparent; border: none; cursor: pointer; width: 32px; height: 32px; border-radius: 6px; color: #64748b; display: flex; align-items: center; justify-content: center; transition: 0.2s; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: white; padding: 2rem; border-radius: 16px; width: 100%; max-width: 640px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25); max-height: 90vh; overflow-y: auto; }
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.modal-header h2 { margin: 0; font-size: 1.3rem; color: #0f172a; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
.form-group { display: flex; flex-direction: column; gap: 0.4rem; }
.form-group label { font-size: 0.85rem; font-weight: 600; color: #475569; }
.label-row { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
.hint { font-size: 0.75rem; color: #94a3b8; }
.required { color: #ef4444; }
.form-input { padding: 0.75rem 1rem; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 0.95rem; background: #f8fafc; outline: none; }
.form-input:disabled { background: #e2e8f0; color: #94a3b8; cursor: not-allowed; }
.form-input:focus:not(:disabled) { border-color: #3b82f6; background: #ffffff; }
.full-width { grid-column: 1 / -1; }

.checkbox-group { flex-direction: row; align-items: center; margin-top: 1rem; grid-column: 1 / -1; }
.checkbox-group input { width: 18px; height: 18px; cursor: pointer; }
.checkbox-group label { cursor: pointer; margin: 0; font-size: 0.95rem; }
.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 2rem; border-top: 1px solid #e2e8f0; padding-top: 1.5rem; }

@media (max-width: 768px) { .form-grid { grid-template-columns: 1fr; } .filters-bar { flex-direction: column; } .search-box, .filter-select { width: 100%; } }
</style>
