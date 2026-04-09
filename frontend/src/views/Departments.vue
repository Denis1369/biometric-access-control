<template>
  <div class="page-container">
    <div class="header-actions">
      <div>
        <h1 class="page-title">Отделы и Графики работы</h1>
        <p class="page-subtitle">Управление структурой компании, рабочим временем и должностями.</p>
      </div>
      <div class="top-buttons">
        <button v-if="canManageDepartments" class="btn-secondary" @click="openGlobalScheduleDialog">
          <i class="pi pi-clock"></i> График для всех
        </button>
        <button v-if="canManageDepartments" class="btn-primary" @click="openNewDialog">
          <i class="pi pi-plus"></i> Добавить отдел
        </button>
      </div>
    </div>

    <DataTable :value="departments" responsiveLayout="scroll" class="p-datatable-sm modern-table">
      <Column field="id" header="ID" sortable style="width: 5%"></Column>
      <Column field="name" header="Название отдела" sortable></Column>
      <Column header="Рабочее время">
        <template #body="slotProps">
          <div class="schedule-badge work">
            <i class="pi pi-sun"></i> 
            {{ slotProps.data.work_start.slice(0,5) }} - {{ slotProps.data.work_end.slice(0,5) }}
          </div>
        </template>
      </Column>
      <Column header="Обеденный перерыв">
        <template #body="slotProps">
          <div class="schedule-badge lunch">
            <i class="pi pi-coffee"></i> 
            {{ slotProps.data.lunch_start.slice(0,5) }} - {{ slotProps.data.lunch_end.slice(0,5) }}
          </div>
        </template>
      </Column>
      <Column header="Действия" style="width: 10%">
        <template #body="slotProps">
          <div v-if="canManageDepartments" class="action-buttons">
            <button class="btn-icon warning" @click="openEditDialog(slotProps.data)" title="Настроить отдел и должности">
              <i class="pi pi-pencil"></i>
            </button>
          </div>
        </template>
      </Column>
    </DataTable>

    <div v-if="displayDialog" class="modal-overlay" @click.self="closeDialog">
      <div class="modal-content" :class="{ 'large-modal': isEditMode, 'small-modal': !isEditMode }">
        <div class="modal-header">
          <h2>{{ isEditMode ? 'Настройки отдела' : 'Новый отдел' }}</h2>
          <button class="btn-icon close-btn" @click="closeDialog"><i class="pi pi-times"></i></button>
        </div>

        <div class="form-group full-width">
          <label>Название отдела <span class="required">*</span></label>
          <input type="text" v-model="deptForm.name" class="form-input" placeholder="Например: Бухгалтерия" />
        </div>

        <h3 class="section-title">График работы</h3>
        <div class="form-grid">
          <div class="form-group">
            <label>Начало работы</label>
            <input type="time" v-model="deptForm.work_start" class="form-input" />
          </div>
          <div class="form-group">
            <label>Конец работы</label>
            <input type="time" v-model="deptForm.work_end" class="form-input" />
          </div>
          <div class="form-group">
            <label>Начало обеда</label>
            <input type="time" v-model="deptForm.lunch_start" class="form-input" />
          </div>
          <div class="form-group">
            <label>Конец обеда</label>
            <input type="time" v-model="deptForm.lunch_end" class="form-input" />
          </div>
        </div>

        <template v-if="isEditMode">
          <h3 class="section-title">Должности отдела</h3>
          <div class="position-editor-row">
            <input v-model="positionForm.name" type="text" class="form-input" placeholder="Название должности" />
            <input v-model.number="positionForm.sort_order" type="number" class="form-input small-input" placeholder="Порядок" />
            <button class="btn-primary" @click="savePosition">{{ positionForm.id ? 'Обновить' : 'Добавить' }}</button>
            <button v-if="positionForm.id" class="btn-text" @click="resetPositionForm">Сбросить</button>
          </div>

          <div class="positions-list">
            <div v-for="position in currentDeptPositions" :key="position.id" class="position-row" :class="{ archived: !position.is_active }">
              <div>
                <div class="position-name">{{ position.name }}</div>
                <div class="position-meta">Порядок: {{ position.sort_order }} · {{ position.is_active ? 'Активна' : 'В архиве' }}</div>
              </div>
              <div class="position-row-actions">
                <button class="btn-icon" @click="editPosition(position)" title="Редактировать">
                  <i class="pi pi-pencil"></i>
                </button>
                <button class="btn-icon" @click="togglePositionArchive(position)" :title="position.is_active ? 'В архив' : 'Вернуть'">
                  <i :class="position.is_active ? 'pi pi-eye-slash' : 'pi pi-refresh'"></i>
                </button>
              </div>
            </div>
            <div v-if="currentDeptPositions.length === 0" class="empty-positions">В этом отделе еще нет добавленных должностей.</div>
          </div>
        </template>
        <div v-else class="global-hint" style="margin-top: 1rem;">
          Сохраните отдел, чтобы появилась возможность добавлять в него должности.
        </div>

        <div class="modal-actions">
          <button class="btn-text" @click="closeDialog">Закрыть</button>
          <button class="btn-primary" @click="saveDepartment">Сохранить отдел</button>
        </div>
      </div>
    </div>

    <div v-if="displayGlobalDialog" class="modal-overlay" @click.self="closeGlobalDialog">
      <div class="modal-content small-modal">
        <div class="modal-header">
          <h2>Единый график для всех отделов</h2>
          <button class="btn-icon close-btn" @click="closeGlobalDialog"><i class="pi pi-times"></i></button>
        </div>
        <p class="global-hint">Внимание: это действие перезапишет индивидуальные графики всех существующих отделов.</p>
        <div class="form-grid">
          <div class="form-group"><label>Начало работы</label><input type="time" v-model="globalSchedule.work_start" class="form-input" /></div>
          <div class="form-group"><label>Конец работы</label><input type="time" v-model="globalSchedule.work_end" class="form-input" /></div>
          <div class="form-group"><label>Начало обеда</label><input type="time" v-model="globalSchedule.lunch_start" class="form-input" /></div>
          <div class="form-group"><label>Конец обеда</label><input type="time" v-model="globalSchedule.lunch_end" class="form-input" /></div>
        </div>
        <div class="modal-actions">
          <button class="btn-text" @click="closeGlobalDialog">Отмена</button>
          <button class="btn-success" @click="applyGlobalSchedule"><i class="pi pi-check"></i> Применить ко всем</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { departmentsApi } from '../api/departments'
import { jobPositionsApi } from '../api/jobPositions'
import { useAuth } from '../services/auth'

const auth = useAuth()
const canManageDepartments = computed(() => auth.hasAnyRole('super_admin'))

const departments = ref([])
const allPositions = ref([])
const displayDialog = ref(false)
const displayGlobalDialog = ref(false)
const isEditMode = ref(false)

const deptForm = ref({ id: null, name: '', work_start: '09:00', work_end: '18:00', lunch_start: '13:00', lunch_end: '14:00' })
const positionForm = ref({ id: null, name: '', sort_order: 100 })
const globalSchedule = ref({ work_start: '09:00', work_end: '18:00', lunch_start: '13:00', lunch_end: '14:00' })

// Фильтруем должности только для текущего редактируемого отдела
const currentDeptPositions = computed(() => {
  if (!deptForm.value.id) return []
  return allPositions.value.filter(p => String(p.department_id) === String(deptForm.value.id)).sort((a,b) => a.sort_order - b.sort_order)
})

const loadData = async () => {
  try {
    const [deptRes, posRes] = await Promise.all([
      departmentsApi.getDepartments(),
      jobPositionsApi.getJobPositions(true)
    ])
    departments.value = deptRes.data
    allPositions.value = posRes.data
  } catch (e) {}
}

const openNewDialog = () => {
  if (!canManageDepartments.value) return
  isEditMode.value = false
  deptForm.value = { id: null, name: '', work_start: '09:00', work_end: '18:00', lunch_start: '13:00', lunch_end: '14:00' }
  displayDialog.value = true
}

const openEditDialog = (dept) => {
  if (!canManageDepartments.value) return
  isEditMode.value = true
  deptForm.value = { ...dept }
  deptForm.value.work_start = dept.work_start.slice(0, 5)
  deptForm.value.work_end = dept.work_end.slice(0, 5)
  deptForm.value.lunch_start = dept.lunch_start.slice(0, 5)
  deptForm.value.lunch_end = dept.lunch_end.slice(0, 5)
  resetPositionForm()
  displayDialog.value = true
}

const closeDialog = () => { displayDialog.value = false }

const saveDepartment = async () => {
  if (!canManageDepartments.value) return
  if (!deptForm.value.name.trim()) return alert('Введите название отдела')
  try {
    const payload = { ...deptForm.value }
    if (isEditMode.value) {
      await departmentsApi.updateDepartment(payload.id, payload)
    } else {
      await departmentsApi.createDepartment(payload)
    }
    closeDialog()
    await loadData()
  } catch (error) { alert('Ошибка при сохранении') }
}

// === ЛОГИКА ДОЛЖНОСТЕЙ ===
const resetPositionForm = () => { positionForm.value = { id: null, name: '', sort_order: 100 } }

const editPosition = (pos) => { positionForm.value = { ...pos } }

const savePosition = async () => {
  if (!positionForm.value.name.trim()) return alert('Введите название должности')
  try {
    const payload = {
      name: positionForm.value.name,
      sort_order: Number(positionForm.value.sort_order || 100),
      department_id: deptForm.value.id // ПРИВЯЗКА К ТЕКУЩЕМУ ОТДЕЛУ
    }
    if (positionForm.value.id) {
      await jobPositionsApi.updateJobPosition(positionForm.value.id, payload)
    } else {
      await jobPositionsApi.createJobPosition(payload)
    }
    resetPositionForm()
    await loadData()
  } catch (error) { alert('Ошибка сохранения должности') }
}

const togglePositionArchive = async (pos) => {
  try {
    await jobPositionsApi.updateJobPosition(pos.id, { is_active: !pos.is_active })
    await loadData()
  } catch (error) { alert('Ошибка обновления') }
}

const openGlobalScheduleDialog = () => { if (canManageDepartments.value) displayGlobalDialog.value = true }
const closeGlobalDialog = () => { displayGlobalDialog.value = false }
const applyGlobalSchedule = async () => {
  if (!canManageDepartments.value) return
  try {
    await departmentsApi.applyGlobalSchedule(globalSchedule.value)
    closeGlobalDialog()
    await loadData()
  } catch (e) { alert('Ошибка') }
}

onMounted(() => { loadData() })
</script>

<style scoped>
.page-container { background: #ffffff; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05); height: 100%; display: flex; flex-direction: column; }
.header-actions { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2rem; }
.page-title { font-size: 1.5rem; font-weight: 600; color: #1e293b; margin: 0; }
.page-subtitle { margin: 0.35rem 0 0; color: #64748b; font-size: 0.9rem; }
.top-buttons { display: flex; gap: 0.75rem; }

.btn-primary, .btn-secondary, .btn-success, .btn-text { border: none; padding: 0.6rem 1.2rem; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 0.5rem; font-weight: 600; transition: all 0.2s; }
.btn-primary { background-color: #3b82f6; color: white; }
.btn-primary:hover { background-color: #2563eb; }
.btn-secondary { background-color: #e2e8f0; color: #334155; }
.btn-secondary:hover { background-color: #cbd5e1; }
.btn-success { background-color: #10b981; color: white; }
.btn-success:hover { background-color: #059669; }
.btn-text { background: transparent; color: #64748b; }
.btn-text:hover { color: #334155; }

.action-buttons { display: flex; gap: 0.5rem; }
.btn-icon { background: transparent; border: none; cursor: pointer; padding: 0.5rem; border-radius: 6px; transition: background-color 0.2s; }
.btn-icon.warning { color: #f59e0b; } .btn-icon.warning:hover { background-color: #fef3c7; }
.close-btn { color: #64748b; font-size: 1.2rem; } .close-btn:hover { background-color: #f1f5f9; color: #0f172a; }

.schedule-badge { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.35rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; }
.schedule-badge.work { background: #e0f2fe; color: #1e40af; }
.schedule-badge.lunch { background: #ffedd5; color: #92400e; }

.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: white; padding: 2rem; border-radius: 16px; width: 100%; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1); max-height: 90vh; overflow-y: auto;}
.small-modal { max-width: 500px; }
.large-modal { max-width: 750px; }
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.modal-header h2 { font-size: 1.35rem; color: #0f172a; margin: 0; }

.section-title { font-size: 1rem; color: #334155; margin: 1.5rem 0 1rem 0; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem; }
.global-hint { font-size: 0.85rem; color: #ef4444; background: #fee2e2; padding: 0.75rem; border-radius: 6px; line-height: 1.4; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
.full-width { grid-column: 1 / -1; }
.form-group { display: flex; flex-direction: column; gap: 0.4rem; }
.form-group label { font-size: 0.85rem; font-weight: 600; color: #475569; }
.required { color: #ef4444; }
.form-input { padding: 0.7rem 0.9rem; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 0.95rem; color: #1e293b; background-color: #f8fafc; }
.form-input:focus { outline: none; border-color: #3b82f6; background-color: #ffffff; }

/* Стили должностей */
.position-editor-row { display: grid; grid-template-columns: 1fr 100px auto auto; gap: 0.75rem; align-items: center; margin-bottom: 1rem; }
.small-input { width: 100%; }
.positions-list { display: flex; flex-direction: column; gap: 0.5rem; max-height: 300px; overflow-y: auto; padding-right: 0.5rem; }
.position-row { display: flex; justify-content: space-between; align-items: center; padding: 0.7rem 1rem; border: 1px solid #e2e8f0; border-radius: 8px; background: #ffffff; }
.position-row.archived { background: #f8fafc; opacity: 0.7; }
.position-name { font-weight: 600; color: #0f172a; font-size: 0.95rem; }
.position-meta { font-size: 0.8rem; color: #64748b; margin-top: 0.1rem; }
.position-row-actions { display: flex; gap: 0.25rem; }
.empty-positions { color: #94a3b8; font-size: 0.9rem; font-style: italic; text-align: center; padding: 1rem; }

.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; padding-top: 2rem; margin-top: 1rem; border-top: 1px solid #e2e8f0; }
</style>