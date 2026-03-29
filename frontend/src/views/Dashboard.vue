<template>
  <div class="dashboard-container">
    <div class="header-actions">
      <h1 class="page-title">Аналитика СКУД</h1>
      <p class="page-subtitle">Безопасность, инфраструктура и HR-отчетность.</p>
    </div>
    
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon bg-blue"><i class="pi pi-users"></i></div>
        <div class="stat-data">
          <span class="stat-label">Всего сотрудников</span>
          <span class="stat-value">{{ stats.total_employees }}</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon bg-green"><i class="pi pi-video"></i></div>
        <div class="stat-data">
          <span class="stat-label">Активные камеры</span>
          <span class="stat-value">{{ stats.active_cameras }}</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon bg-orange"><i class="pi pi-sign-in"></i></div>
        <div class="stat-data">
          <span class="stat-label">Проходов за день</span>
          <span class="stat-value">{{ stats.accesses_today }}</span>
        </div>
      </div>
      <div class="stat-card presence-card">
        <div class="stat-icon bg-purple"><i class="pi pi-check-square"></i></div>
        <div class="stat-data full-width">
          <span class="stat-label">Присутствие сегодня</span>
          <div class="presence-values">
            <span class="stat-value">{{ presence.present }} / {{ presence.total }}</span>
            <span class="stat-percent">{{ presence.percentage }}%</span>
          </div>
          <div class="progress-bg">
            <div class="progress-fill" :style="{ width: presence.percentage + '%' }"></div>
          </div>
        </div>
      </div>
    </div>

    <div class="charts-grid-half">
      <div class="chart-card">
        <div class="chart-header">
          <h3>HR: Дисциплина за месяц</h3>
          <button v-if="disciplineLevel === 'employees'" @click="backToDepartments" class="btn-back">
            <i class="pi pi-arrow-left"></i> Назад к отделам
          </button>
        </div>
        <p class="chart-hint" v-if="disciplineLevel === 'departments'">Кликните по столбцу отдела для детализации по сотрудникам.</p>
        <p class="chart-hint" v-else>Детализация по отделу: <b>{{ selectedDeptName }}</b></p>
        
        <Chart type="bar" :data="disciplineChartData" :options="disciplineOptions" class="chart-element" />
      </div>

      <div class="chart-card">
        <h3>Нагрузка на точки прохода (за месяц)</h3>
        <Chart type="bar" :data="cameraTrafficData" :options="cameraTrafficOptions" class="chart-element" />
      </div>
    </div>

    <div class="charts-grid">
      <div class="chart-card">
        <h3>Динамика активности по часам (Сегодня)</h3>
        <Chart type="bar" :data="dailyChartData" :options="dailyChartOptions" class="chart-element" />
      </div>
      <div class="chart-card">
        <h3>Проходы по отделам</h3>
        <div v-if="deptChartData.labels.length > 0">
          <Chart type="doughnut" :data="deptChartData" :options="deptChartOptions" class="chart-element doughnut" />
        </div>
      </div>
    </div>

    <div class="chart-card full-width-chart">
      <h3>Активность по дням (Текущий месяц)</h3>
      <Chart type="line" :data="monthlyDaysChartData" :options="monthlyDaysChartOptions" class="chart-element" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import Chart from 'primevue/chart'
import { analyticsApi } from '../api/analytics'

const stats = ref({ total_employees: 0, active_cameras: 0, accesses_today: 0 })
const presence = ref({ present: 0, total: 0, percentage: 0 })

const rawDisciplineData = ref([])
const disciplineLevel = ref('departments')
const selectedDeptName = ref('')

const dailyChartData = ref({ labels: [], datasets: [] })
const dailyChartOptions = ref({ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } })

const deptChartData = ref({ labels: [], datasets: [] })
const deptChartOptions = ref({ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } })

const monthlyDaysChartData = ref({ labels: [], datasets: [] })
const monthlyDaysChartOptions = ref({ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } })

const cameraTrafficData = ref({ labels: [], datasets: [] })
const cameraTrafficOptions = ref({
  indexAxis: 'y',
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } }
})

const loadDashboardData = async () => {
  try {
    const [statsRes, presenceRes, trafficRes, disciplineRes, dailyRes, deptRes, daysRes] = await Promise.all([
      analyticsApi.getStats(),
      analyticsApi.getPresence(),
      analyticsApi.getCameraTraffic(),
      analyticsApi.getDiscipline(),
      analyticsApi.getDailyChart(),
      analyticsApi.getMonthlyDepartmentChart(),
      analyticsApi.getMonthlyDaysChart()
    ])
    
    stats.value = statsRes.data
    presence.value = presenceRes.data
    rawDisciplineData.value = disciplineRes.data

    cameraTrafficData.value = {
      labels: trafficRes.data.labels,
      datasets: [{
        label: 'Количество проходов',
        backgroundColor: '#8b5cf6',
        borderRadius: 4,
        data: trafficRes.data.data
      }]
    }

    dailyChartData.value = {
      labels: dailyRes.data.labels,
      datasets: [{ label: 'Проходы', backgroundColor: '#3b82f6', borderRadius: 4, data: dailyRes.data.data }]
    }
    deptChartData.value = {
      labels: deptRes.data.labels,
      datasets: [{
        data: deptRes.data.data,
        backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6']
      }]
    }
    monthlyDaysChartData.value = {
      labels: daysRes.data.labels,
      datasets: [{
        label: 'Проходы за день', borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.15)',
        fill: true, tension: 0.4, data: daysRes.data.data
      }]
    }

  } catch (error) {
    console.error(error)
  }
}

const disciplineChartData = computed(() => {
  let labels = []
  let onTimeData = []
  let lateData = []

  if (disciplineLevel.value === 'departments') {
    rawDisciplineData.value.forEach(dept => {
      labels.push(dept.department_name)
      onTimeData.push(dept.on_time)
      lateData.push(dept.late)
    })
  } else {
    const dept = rawDisciplineData.value.find(d => d.department_name === selectedDeptName.value)
    if (dept) {
      dept.employees.forEach(emp => {
        labels.push(emp.employee_name)
        onTimeData.push(emp.on_time)
        lateData.push(emp.late)
      })
    }
  }

  return {
    labels,
    datasets: [
      { label: 'Опоздания', backgroundColor: '#ef4444', data: lateData }
    ]
  }
})

const disciplineOptions = ref({
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    x: { stacked: true, grid: { display: false } },
    y: { stacked: true, beginAtZero: true, ticks: { stepSize: 1 } }
  },
  onClick: (event, elements) => {
    if (elements.length > 0 && disciplineLevel.value === 'departments') {
      const clickedIndex = elements[0].index
      const deptName = disciplineChartData.value.labels[clickedIndex]
      selectedDeptName.value = deptName
      disciplineLevel.value = 'employees'
    }
  }
})

const backToDepartments = () => {
  disciplineLevel.value = 'departments'
}

onMounted(() => { loadDashboardData() })
</script>

<style scoped>
.dashboard-container { display: flex; flex-direction: column; gap: 1.5rem; padding-bottom: 2rem;}
.header-actions { margin-bottom: 0.5rem; }
.page-title { font-size: 1.5rem; font-weight: 600; color: #0f172a; margin: 0; }
.page-subtitle { margin: 0.35rem 0 0; color: #64748b; font-size: 0.95rem; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.5rem; }
.stat-card { background: #ffffff; padding: 1.25rem 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; display: flex; align-items: center; gap: 1.2rem; }
.stat-icon { width: 50px; height: 50px; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.4rem; flex-shrink: 0;}
.bg-blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
.bg-green { background: linear-gradient(135deg, #10b981, #059669); }
.bg-orange { background: linear-gradient(135deg, #f59e0b, #d97706); }
.bg-purple { background: linear-gradient(135deg, #8b5cf6, #6d28d9); }

.stat-data { display: flex; flex-direction: column; }
.full-width { flex: 1; }
.stat-label { font-size: 0.85rem; color: #64748b; font-weight: 600; margin-bottom: 0.2rem; }
.stat-value { font-size: 1.6rem; font-weight: 700; color: #0f172a; }

.presence-values { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 0.4rem;}
.stat-percent { font-size: 1.2rem; font-weight: 700; color: #8b5cf6; }
.progress-bg { width: 100%; height: 6px; background: #e2e8f0; border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; background: #8b5cf6; transition: width 0.5s ease-out; }

.charts-grid-half { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
.charts-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem; }

.chart-card { background: #ffffff; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; }
.chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem; }
.chart-card h3 { font-size: 1.1rem; margin: 0; color: #0f172a; }
.chart-hint { font-size: 0.8rem; color: #64748b; margin: 0 0 1rem 0; }

.btn-back { background: #f1f5f9; border: 1px solid #cbd5e1; color: #334155; padding: 0.3rem 0.6rem; border-radius: 6px; cursor: pointer; font-size: 0.8rem; font-weight: 600; display: flex; align-items: center; gap: 0.3rem; transition: background 0.2s;}
.btn-back:hover { background: #e2e8f0; }

.chart-element { height: 300px; width: 100%; }
.chart-element.doughnut { height: 260px; }
.full-width-chart { grid-column: 1 / -1; margin-top: 0; }

@media (max-width: 1200px) {
  .charts-grid-half, .charts-grid { grid-template-columns: 1fr; }
}
</style>