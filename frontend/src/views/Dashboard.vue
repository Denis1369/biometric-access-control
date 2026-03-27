<template>
  <div class="dashboard">
    <h1 class="page-title">Обзор системы</h1>
    
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon"><i class="pi pi-users"></i></div>
        <div class="stat-data">
          <span class="stat-label">Всего сотрудников</span>
          <span class="stat-value">{{ stats.total_employees }}</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon"><i class="pi pi-video"></i></div>
        <div class="stat-data">
          <span class="stat-label">Активные камеры</span>
          <span class="stat-value">{{ stats.active_cameras }}</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon"><i class="pi pi-sign-in"></i></div>
        <div class="stat-data">
          <span class="stat-label">Проходов за день</span>
          <span class="stat-value">{{ stats.accesses_today }}</span>
        </div>
      </div>
    </div>

    <div class="logs-section">
      <h2>Последние события</h2>
      <DataTable :value="logs" responsiveLayout="scroll" class="p-datatable-sm">
        <Column field="timestamp" header="Время"></Column>
        <Column field="employee_name" header="Сотрудник"></Column>
        <Column field="camera_name" header="Камера"></Column>
        <Column field="status" header="Статус">
          <template #body="slotProps">
            <span :class="['status-badge', slotProps.data.status === 'granted' ? 'granted' : 'denied']">
              {{ slotProps.data.status === 'granted' ? 'Доступ разрешен' : 'Отказ' }}
            </span>
          </template>
        </Column>
      </DataTable>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import { analyticsApi } from '../api/analytics'

const stats = ref({ total_employees: 0, active_cameras: 0, accesses_today: 0 })
const logs = ref([])

const fetchStats = async () => {
  try {
    const response = await analyticsApi.getStats()
    stats.value = response.data
  } catch (error) {}
}

const fetchLogs = async () => {
  try {
    const response = await analyticsApi.getAccessLogs(5)
    logs.value = response.data.map(log => ({
      ...log,
      timestamp: new Date(log.timestamp).toLocaleTimeString('ru-RU', { 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
      })
    }))
  } catch (error) {}
}

onMounted(() => {
  fetchStats()
  fetchLogs()
})
</script>

<style scoped>
.page-title {
  font-size: 1.5rem;
  color: #1e293b;
  margin-bottom: 1.5rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.stat-card {
  background: #ffffff;
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #475569;
  font-size: 1.5rem;
}

.stat-data {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 0.875rem;
  color: #64748b;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 600;
  color: #0f172a;
}

.logs-section {
  background: #ffffff;
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.logs-section h2 {
  font-size: 1.25rem;
  margin-bottom: 1.25rem;
  color: #1e293b;
}

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.status-badge.granted {
  background: #dcfce7;
  color: #166534;
}

.status-badge.denied {
  background: #fee2e2;
  color: #991b1b;
}
</style>