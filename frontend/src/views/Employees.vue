<template>
  <div class="page-container">
    <div class="header-actions">
      <h1 class="page-title">Сотрудники</h1>
      <button class="btn-primary" @click="openNewDialog">
        <i class="pi pi-plus"></i> Добавить
      </button>
    </div>

    <DataTable :value="employees" responsiveLayout="scroll" class="p-datatable-sm">
      <Column field="id" header="ID" sortable></Column>
      <Column header="Фамилия">
        <template #body="slotProps">
          {{ slotProps.data.last_name }}
        </template>
      </Column>
      <Column header="Имя">
        <template #body="slotProps">
          {{ slotProps.data.first_name }}
        </template>
      </Column>
      <Column header="Отчество">
        <template #body="slotProps">
          {{ slotProps.data.middle_name || '-' }}
        </template>
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
          <button class="btn-icon danger" @click="confirmDelete(slotProps.data.id)">
            <i class="pi pi-trash"></i>
          </button>
        </template>
      </Column>
    </DataTable>

    <div v-if="displayDialog" class="modal-overlay">
      <div class="modal-content">
        <h2>Новый сотрудник</h2>
        
        <div class="form-group">
          <label>Фамилия *</label>
          <input type="text" v-model="employeeForm.last_name" class="form-input" />
        </div>
        
        <div class="form-group">
          <label>Имя *</label>
          <input type="text" v-model="employeeForm.first_name" class="form-input" />
        </div>
        
        <div class="form-group">
          <label>Отчество</label>
          <input type="text" v-model="employeeForm.middle_name" class="form-input" />
        </div>

        <div class="form-group">
          <label>Отдел *</label>
          <select v-model="employeeForm.department_id" class="form-input">
            <option v-for="dept in departments" :key="dept.id" :value="dept.id">
              {{ dept.name }}
            </option>
          </select>
        </div>

        <div class="form-group">
          <label>Фотография лица (строго анфас) *</label>
          <input type="file" accept="image/*" @change="onFileSelect" class="form-input file-input" />
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
import { ref, onMounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { employeesApi } from '../api/employees'
import { departmentsApi } from '../api/departments'

const employees = ref([])
const departments = ref([])
const displayDialog = ref(false)
const selectedFile = ref(null)

const employeeForm = ref({
  last_name: '',
  first_name: '',
  middle_name: '',
  department_id: ''
})

const loadData = async () => {
  try {
    const [empRes, depRes] = await Promise.all([
      employeesApi.getEmployees(),
      departmentsApi.getDepartments()
    ])
    employees.value = empRes.data
    departments.value = depRes.data
  } catch (error) {}
}

const openNewDialog = () => {
  employeeForm.value = { last_name: '', first_name: '', middle_name: '', department_id: '' }
  selectedFile.value = null
  displayDialog.value = true
}

const closeDialog = () => {
  displayDialog.value = false
}

const onFileSelect = (event) => {
  selectedFile.value = event.target.files[0]
}

const saveEmployee = async () => {
  if (!employeeForm.value.last_name || !employeeForm.value.first_name || !selectedFile.value || !employeeForm.value.department_id) {
    alert('Заполните все обязательные поля и выберите фото')
    return
  }

  const formData = new FormData()
  formData.append('last_name', employeeForm.value.last_name.trim())
  formData.append('first_name', employeeForm.value.first_name.trim())
  
  if (employeeForm.value.middle_name) {
    formData.append('middle_name', employeeForm.value.middle_name.trim())
  }
  
  formData.append('department_id', employeeForm.value.department_id)
  formData.append('photo', selectedFile.value)

  try {
    await employeesApi.createEmployee(formData)
    closeDialog()
    await loadData()
  } catch (error) {
    alert('Ошибка при сохранении. Убедитесь, что на фото есть лицо.')
  }
}

const confirmDelete = async (id) => {
  if (confirm('Точно удалить сотрудника?')) {
    try {
      await employeesApi.deleteEmployee(id)
      await loadData()
    } catch (error) {}
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.page-container {
  background: #ffffff;
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.page-title {
  font-size: 1.25rem;
  color: #1e293b;
}

.btn-primary {
  background-color: #10b981;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
}

.btn-primary:hover {
  background-color: #059669;
}

.btn-text {
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem 1rem;
  font-weight: 500;
}

.btn-icon {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 4px;
}

.btn-icon.danger {
  color: #ef4444;
}

.btn-icon.danger:hover {
  background-color: #fee2e2;
}

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.status-badge.active {
  background: #dcfce7;
  color: #166534;
}

.status-badge.inactive {
  background: #f1f5f9;
  color: #475569;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  width: 100%;
  max-width: 500px;
}

.modal-content h2 {
  margin-bottom: 1.5rem;
  font-size: 1.25rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  color: #475569;
}

.form-input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  font-size: 1rem;
}

.file-input {
  border: none;
  padding: 0;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 2rem;
}
</style>