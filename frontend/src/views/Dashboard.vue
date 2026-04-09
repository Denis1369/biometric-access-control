<template>
  <div class="dashboard-container">
    <div class="header-section">
      <div>
        <h1 class="page-title">Аналитика СКУД</h1>
        <p class="page-subtitle">Безопасность, инфраструктура и HR-отчетность.</p>
      </div>
      <div class="global-date-picker">
        <input 
          type="date" 
          v-model="globalDate" 
          @change="onGlobalDateChange" 
          class="date-picker-input global-input" 
          title="Выберите день для просмотра статистики"
        />
      </div>
    </div>

    <div class="reports-section card-box">
      <div class="reports-header">
        <div class="reports-titles">
          <h3>Отчеты и посещаемость</h3>
          <p class="chart-hint">Контроль присутствия, опозданий и гостевых визитов по дням.</p>
        </div>
        
        <div class="reports-controls">
          <div class="tabs-container">
            <button class="tab-btn" :class="{ active: activeTab === 'employees' }" @click="activeTab = 'employees'">
              <i class="pi pi-users"></i> Сотрудники
            </button>
            <button class="tab-btn" :class="{ active: activeTab === 'guests' }" @click="activeTab = 'guests'">
              <i class="pi pi-id-card"></i> Гости
            </button>
          </div>

          <div v-if="activeTab === 'employees'" class="filter-group">
            <select v-model="selectedReportDept" class="date-picker-input dept-select">
              <option value="all">Все отделы</option>
              <option v-for="dept in departmentsForFilter" :key="dept.id" :value="dept.id">
                {{ dept.name }}
              </option>
            </select>

            <select v-model="selectedStatus" class="date-picker-input dept-select">
              <option value="all">Все статусы</option>
              <option value="working">На работе</option>
              <option value="left">Смена закрыта</option>
              <option value="absent">Отсутствует</option>
            </select>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'employees'" class="table-responsive">
        <table class="modern-table">
          <thead>
            <tr>
              <th>Сотрудник</th>
              <th>Отдел</th>
              <th>Приход</th>
              <th>Уход</th>
              <th>Статус дня</th>
              <th>Нарушения</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="emp in filteredEmployees" :key="emp.id" :class="{ 'row-absent': emp.status === 'absent' }">
              <td class="fw-bold">{{ emp.name }}</td>
              <td>{{ getDeptName(emp.department_id) }}</td>
              <td>
                <span v-if="emp.time_in" class="time-badge in"><i class="pi pi-sign-in"></i> {{ emp.time_in }}</span>
                <span v-else class="text-muted">—</span>
              </td>
              <td>
                <span v-if="emp.time_out" class="time-badge out"><i class="pi pi-sign-out"></i> {{ emp.time_out }}</span>
                <span v-else class="text-muted">—</span>
              </td>
              <td>
                <span v-if="emp.status === 'absent'" class="status-badge absent">Отсутствует</span>
                <span v-else-if="emp.status === 'working'" class="status-badge working">На работе</span>
                <span v-else-if="emp.status === 'left'" class="status-badge left">Смена закрыта</span>
              </td>
              <td>
                <div class="violations-stack">
                  <span v-if="emp.is_late" class="violation-badge late">Опоздание</span>
                  <span v-if="emp.left_early" class="violation-badge early">Ушел раньше</span>
                  <span v-if="!emp.is_late && !emp.left_early && emp.status !== 'absent'" class="text-success"><i class="pi pi-check-circle"></i> Ок</span>
                </div>
              </td>
            </tr>
            <tr v-if="filteredEmployees.length === 0">
              <td colspan="6" class="empty-state">Нет данных по выбранным фильтрам</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="activeTab === 'guests'" class="table-responsive">
        <table class="modern-table">
          <thead>
            <tr>
              <th>Гость (ФИО)</th>
              <th>К кому пришел</th>
              <th>Приход</th>
              <th>Уход</th>
              <th>Время внутри</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="guest in filteredGuests" :key="guest.id">
              <td class="fw-bold">{{ guest.name }}</td>
              <td><i class="pi pi-user text-muted"></i> {{ guest.visited_employee }}</td>
              <td>
                <span v-if="guest.time_in" class="time-badge in"><i class="pi pi-sign-in"></i> {{ guest.time_in }}</span>
              </td>
              <td>
                <span v-if="guest.time_out" class="time-badge out"><i class="pi pi-sign-out"></i> {{ guest.time_out }}</span>
                <span v-else class="status-badge working">Еще внутри</span>
              </td>
              <td>
                <span v-if="guest.duration" class="duration-badge"><i class="pi pi-clock"></i> {{ guest.duration }}</span>
                <span v-else class="text-muted">Считается...</span>
              </td>
            </tr>
            <tr v-if="filteredGuests.length === 0">
              <td colspan="5" class="empty-state">В этот день гостей не было</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="charts-grid-half">
      <div class="chart-card">
        <div class="chart-header">
          <h3>HR: Дисциплина за месяц</h3>
          <select v-model="disciplineView" class="date-picker-input dept-select">
            <option value="all">Обзор всех отделов</option>
            <option v-for="dept in departmentList" :key="dept" :value="dept">
              {{ dept }}
            </option>
          </select>
        </div>
        <Chart type="bar" :data="disciplineChartData" :options="disciplineOptions" class="chart-element" />
      </div>

      <div class="chart-card">
        <h3>Динамика активности по часам (За день)</h3>
        <Chart type="bar" :data="dailyChartData" :options="dailyChartOptions" class="chart-element" />
      </div>
    </div>

    <div class="charts-grid">
      <div class="chart-card full-width-chart">
        <h3>Активность по дням (Текущий месяц)</h3>
        <Chart type="line" :data="monthlyDaysChartData" :options="monthlyDaysChartOptions" class="chart-element" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import Chart from 'primevue/chart'
import { analyticsApi } from '../api/analytics'

const globalDate = ref(new Date().toISOString().split('T')[0]) // Текущая дата по умолчанию

const activeTab = ref('employees')
const selectedReportDept = ref('all')
const selectedStatus = ref('all')

const departmentsForFilter = ref([
  { id: 1, name: 'Администрация' },
  { id: 2, name: 'ИТ-отдел' },
  { id: 3, name: 'Служба безопасности' }
])

const getDeptName = (id) => {
  const d = departmentsForFilter.value.find(d => d.id === id)
  return d ? d.name : '—'
}

const apiEmployeesData = ref([])
const apiGuestsData = ref([])

const filteredEmployees = computed(() => {
  return apiEmployeesData.value.filter(emp => {
    const matchDept = selectedReportDept.value === 'all' || emp.department_id === selectedReportDept.value
    const matchStatus = selectedStatus.value === 'all' || emp.status === selectedStatus.value
    return matchDept && matchStatus
  })
})

const filteredGuests = computed(() => apiGuestsData.value)

const rawDisciplineData = ref([])
const disciplineLevel = ref('departments')
const selectedDeptName = ref('')

const dailyChartData = ref({ labels: [], datasets: [] })
const dailyChartOptions = ref({ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } })

const monthlyDaysChartData = ref({ labels: [], datasets: [] })
const monthlyDaysChartOptions = ref({ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } })

const departmentList = computed(() => rawDisciplineData.value.map(d => d.department_name))

const disciplineView = computed({
  get() { return disciplineLevel.value === 'departments' ? 'all' : selectedDeptName.value },
  set(val) {
    if (val === 'all') { disciplineLevel.value = 'departments'; selectedDeptName.value = '' } 
    else { selectedDeptName.value = val; disciplineLevel.value = 'employees' }
  }
})

const disciplineChartData = computed(() => {
  let labels = [], onTimeData = [], lateData = []
  if (disciplineLevel.value === 'departments') {
    rawDisciplineData.value.forEach(dept => { labels.push(dept.department_name); onTimeData.push(dept.on_time); lateData.push(dept.late) })
  } else {
    const dept = rawDisciplineData.value.find(d => d.department_name === selectedDeptName.value)
    if (dept) { dept.employees.forEach(emp => { labels.push(emp.employee_name); onTimeData.push(emp.on_time); lateData.push(emp.late) }) }
  }
  return {
    labels,
    datasets: [
      { label: 'Вовремя', backgroundColor: '#10b981', data: onTimeData },
      { label: 'Опоздания', backgroundColor: '#ef4444', data: lateData }
    ]
  }
})

const disciplineOptions = ref({
  responsive: true, maintainAspectRatio: false,
  scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, ticks: { stepSize: 1 } } },
  onClick: (event, elements) => {
    if (elements.length > 0 && disciplineLevel.value === 'departments') {
      disciplineView.value = disciplineChartData.value.labels[elements[0].index]
    }
  }
})

const updateDailyWidgets = (dailyRes, employeesRes, guestsRes) => {
  apiEmployeesData.value = employeesRes.data
  apiGuestsData.value = guestsRes.data
  dailyChartData.value = {
    labels: dailyRes.data.labels,
    datasets: [{ label: 'Проходы', backgroundColor: '#3b82f6', borderRadius: 4, data: dailyRes.data.data }]
  }
}

const onGlobalDateChange = async () => {
  try {
    const [dailyRes, employeesRes, guestsRes] = await Promise.all([
      analyticsApi.getDailyChart(globalDate.value),
      analyticsApi.getDailyAttendance(globalDate.value),
      analyticsApi.getDailyGuests(globalDate.value)
    ])
    updateDailyWidgets(dailyRes, employeesRes, guestsRes)
  } catch (error) { console.error(error) }
}

const loadDashboardData = async () => {
  try {
    const [dailyRes, disciplineRes, daysRes, employeesRes, guestsRes] = await Promise.all([
      analyticsApi.getDailyChart(globalDate.value),
      analyticsApi.getDiscipline(),
      analyticsApi.getMonthlyDaysChart(),
      analyticsApi.getDailyAttendance(globalDate.value),
      analyticsApi.getDailyGuests(globalDate.value)
    ])
    
    updateDailyWidgets(dailyRes, employeesRes, guestsRes)
    rawDisciplineData.value = disciplineRes.data

    monthlyDaysChartData.value = {
      labels: daysRes.data.labels,
      datasets: [{
        label: 'Проходы за день', borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.15)',
        fill: true, tension: 0.4, data: daysRes.data.data
      }]
    }
  } catch (error) { console.error(error) }
}

onMounted(() => { loadDashboardData() })
</script>

<style scoped>
.dashboard-container { display: flex; flex-direction: column; gap: 1.5rem; padding-bottom: 2rem;}
.header-section { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.page-title { font-size: 1.5rem; font-weight: 600; color: #0f172a; margin: 0; }
.page-subtitle { margin: 0.35rem 0 0; color: #64748b; font-size: 0.95rem; }

.card-box { background: #ffffff; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; }
.reports-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 1rem; }
.reports-titles h3 { font-size: 1.25rem; margin: 0 0 0.2rem 0; color: #0f172a; }
.reports-controls { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; }
.filter-group { display: flex; gap: 0.75rem; }

.tabs-container { display: flex; gap: 0.5rem; background: #f1f5f9; padding: 0.3rem; border-radius: 10px; }
.tab-btn { background: transparent; border: none; padding: 0.5rem 1rem; border-radius: 8px; font-weight: 600; color: #64748b; cursor: pointer; transition: 0.2s; display: flex; align-items: center; gap: 0.5rem; }
.tab-btn:hover { color: #0f172a; }
.tab-btn.active { background: #ffffff; color: #0f172a; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }

.table-responsive { 
  overflow-x: auto; 
  overflow-y: auto;
  max-height: 400px;
  border-bottom: 1px solid #e2e8f0;
}

.modern-table { 
  width: 100%; 
  border-collapse: collapse; 
  text-align: left; 
}

.modern-table th { 
  background: #f8fafc; 
  padding: 1rem; 
  font-size: 0.85rem; 
  font-weight: 700; 
  color: #475569; 
  text-transform: uppercase; 
  position: sticky; 
  top: 0; 
  z-index: 10; 
  box-shadow: inset 0 -1px 0 #e2e8f0; 
}.modern-table td { padding: 1rem; font-size: 0.95rem; color: #1e293b; border-bottom: 1px solid #e2e8f0; vertical-align: middle; }
.fw-bold { font-weight: 600; color: #0f172a; }
.text-muted { color: #94a3b8; }
.text-success { color: #10b981; font-weight: 600; font-size: 0.9rem; }

.row-absent td { background: #fafafa; color: #94a3b8; }
.row-absent .fw-bold { color: #64748b; }

.time-badge { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.3rem 0.6rem; border-radius: 6px; font-family: monospace; font-size: 0.9rem; font-weight: 600; }
.time-badge.in { background: #f0fdf4; color: #166534; }
.time-badge.out { background: #fff1f2; color: #991b1b; }
.duration-badge { background: #eff6ff; color: #1e40af; padding: 0.3rem 0.6rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; display: inline-flex; align-items: center; gap: 0.35rem; }

.status-badge { padding: 0.35rem 0.75rem; border-radius: 999px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }
.status-badge.working { background: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }
.status-badge.left { background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }
.status-badge.absent { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }

.violations-stack { display: flex; flex-direction: column; gap: 0.4rem; align-items: flex-start; }
.violation-badge { padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.75rem; font-weight: 700; display: inline-block; }
.violation-badge.late { background: #fef3c7; color: #b45309; }
.violation-badge.early { background: #ffedd5; color: #c2410c; }
.empty-state { text-align: center; padding: 2rem !important; color: #94a3b8; font-style: italic; }

.charts-grid-half { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 1.5rem;}
.charts-grid { display: grid; grid-template-columns: 1fr; gap: 1.5rem; margin-top: 1.5rem;}

.chart-card { background: #ffffff; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; }
.chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem; }
.chart-card h3 { font-size: 1.1rem; margin: 0; color: #0f172a; margin-bottom: 1rem;}

.date-picker-input { padding: 0.35rem 0.6rem; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 0.85rem; color: #475569; background: #f8fafc; cursor: pointer; outline: none; }
.date-picker-input:focus { border-color: #3b82f6; }
.global-input { padding: 0.5rem 1rem; font-size: 1rem; font-weight: 600; color: #0f172a; border-color: #e2e8f0; }

.chart-element { height: 300px; width: 100%; }

@media (max-width: 1200px) {
  .charts-grid-half { grid-template-columns: 1fr; }
  .header-section { flex-direction: column; align-items: flex-start; gap: 1rem; }
  .reports-header { flex-direction: column; align-items: flex-start; }
}
@media (max-width: 768px) {
  .filter-group { flex-direction: column; width: 100%; }
  .dept-select { width: 100%; }
}
</style>