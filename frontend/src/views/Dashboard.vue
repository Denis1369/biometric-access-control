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
          <span class="stat-label">Присутствие за день</span>
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
          <h3>Контроль рабочего времени</h3>
          <div class="header-controls">
            <select v-model="selectedAttendanceDept" class="date-picker-input dept-select">
              <option value="all">Все отделы</option>
              <option v-for="dept in attendanceDepartments" :key="dept" :value="dept">
                {{ dept }}
              </option>
            </select>
          </div>
        </div>
        <p class="chart-hint">
          <span class="legend-dot green"></span> В норме
          <span class="legend-dot red"></span> Нарушение (Опоздание / Ранний уход)
        </p>

        <div v-if="attendanceChartData.datasets && attendanceChartData.datasets.length > 0" class="scrollable-chart-container">
          <div :style="{ height: dynamicChartHeight + 'px', position: 'relative', width: '100%' }">
            <Chart 
              type="bar" 
              :data="attendanceChartData" 
              :options="attendanceOptions" 
              style="height: 100%; width: 100%;" 
            />
          </div>
        </div>
        
        <div v-else class="empty-chart" style="height: 300px;">
          <i class="pi pi-inbox" style="font-size: 2.5rem; margin-bottom: 1rem; color: #cbd5e1;"></i>
          <p>Нет зафиксированных проходов<br>за выбранную дату (или в отделе)</p>
        </div>
      </div>

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
    </div>

    <div class="charts-grid">
      <div class="chart-card">
        <h3>Динамика активности по часам (За день)</h3>
        <Chart type="bar" :data="dailyChartData" :options="dailyChartOptions" class="chart-element" />
      </div>
      
      <div class="chart-card">
        <h3>Нагрузка на точки прохода (за месяц)</h3>
        <Chart type="bar" :data="cameraTrafficData" :options="cameraTrafficOptions" class="chart-element" />
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

const globalDate = ref('')

const stats = ref({ total_employees: 0, active_cameras: 0, accesses_today: 0 })
const presence = ref({ present: 0, total: 0, percentage: 0 })

const rawAttendanceData = ref([])
const selectedAttendanceDept = ref('all')

const rawDisciplineData = ref([])
const disciplineLevel = ref('departments')
const selectedDeptName = ref('')

const dailyChartData = ref({ labels: [], datasets: [] })
const dailyChartOptions = ref({ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } })

const monthlyDaysChartData = ref({ labels: [], datasets: [] })
const monthlyDaysChartOptions = ref({ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } })

const cameraTrafficData = ref({ labels: [], datasets: [] })
const cameraTrafficOptions = ref({
  indexAxis: 'y',
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } }
})

const attendanceDepartments = computed(() => {
  const depts = new Set(rawAttendanceData.value.map(r => r.department))
  return Array.from(depts).sort()
})

const filteredAttendanceRecords = computed(() => {
  let records = rawAttendanceData.value
  if (selectedAttendanceDept.value !== 'all') {
    records = records.filter(r => r.department === selectedAttendanceDept.value)
  }
  return records
})

const attendanceChartData = computed(() => {
  const records = filteredAttendanceRecords.value
  if (records.length === 0) return { labels: [], datasets: [] }

  const attendancePoints = records.map(r => {
    let end = r.departure_dec
    if (end === r.arrival_dec) end += 0.15 
    return [r.arrival_dec, end]
  })

  return {
    labels: records.map(r => r.employee),
    datasets: [{
      label: 'Время в офисе',
      data: attendancePoints,
      backgroundColor: records.map(r => (r.is_late || r.is_left_early) ? '#ef4444' : '#10b981'),
      borderRadius: 4,
      borderSkipped: false
    }]
  }
})

const attendanceOptions = computed(() => {
  const records = filteredAttendanceRecords.value
  return {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: function(context) {
            const emp = records[context.dataIndex]
            let statusArr = []
            if (emp.is_late) statusArr.push('Опоздал')
            if (emp.is_left_early) statusArr.push('Ушёл раньше')
            
            const status = statusArr.length > 0 ? statusArr.join(', ') : 'Вовремя'
            return ` Приход: ${emp.arrival} | Уход: ${emp.departure} (${status})`
          },
          afterLabel: function(context) {
            const emp = records[context.dataIndex]
            return ` Отдел: ${emp.department} (График: ${emp.work_start} - ${emp.work_end})`
          }
        }
      }
    },
    scales: {
      x: {
        min: 6,
        max: 23,
        ticks: {
          stepSize: 2,
          callback: function(value) { return `${value.toString().padStart(2, '0')}:00` }
        },
        grid: { color: '#f1f5f9' }
      },
      y: { grid: { display: false } }
    }
  }
})

const dynamicChartHeight = computed(() => {
  const count = attendanceChartData.value.labels?.length || 0
  return Math.max(300, count * 40)
})

const departmentList = computed(() => {
  return rawDisciplineData.value.map(d => d.department_name)
})

const disciplineView = computed({
  get() {
    return disciplineLevel.value === 'departments' ? 'all' : selectedDeptName.value
  },
  set(val) {
    if (val === 'all') {
      disciplineLevel.value = 'departments'
      selectedDeptName.value = ''
    } else {
      selectedDeptName.value = val
      disciplineLevel.value = 'employees'
    }
  }
})

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
      { label: 'Вовремя', backgroundColor: '#10b981', data: onTimeData },
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
      disciplineView.value = deptName
    }
  }
})

const updateDailyWidgets = (statsRes, presenceRes, attendanceRes, dailyRes) => {
  stats.value = statsRes.data
  presence.value = presenceRes.data
  rawAttendanceData.value = attendanceRes.data.data || []
  
  dailyChartData.value = {
    labels: dailyRes.data.labels,
    datasets: [{ label: 'Проходы', backgroundColor: '#3b82f6', borderRadius: 4, data: dailyRes.data.data }]
  }
}

const onGlobalDateChange = async () => {
  try {
    const [statsRes, presenceRes, attendanceRes, dailyRes] = await Promise.all([
      analyticsApi.getStats(globalDate.value),
      analyticsApi.getPresence(globalDate.value),
      analyticsApi.getDailyAttendance(globalDate.value),
      analyticsApi.getDailyChart(globalDate.value)
    ])
    updateDailyWidgets(statsRes, presenceRes, attendanceRes, dailyRes)
  } catch (error) {
    console.error(error)
  }
}

const loadDashboardData = async () => {
  try {
    const attendanceResFirst = await analyticsApi.getDailyAttendance()
    globalDate.value = attendanceResFirst.data.date

    const [statsRes, presenceRes, trafficRes, dailyRes, disciplineRes, daysRes] = await Promise.all([
      analyticsApi.getStats(globalDate.value),
      analyticsApi.getPresence(globalDate.value),
      analyticsApi.getCameraTraffic(),
      analyticsApi.getDailyChart(globalDate.value),
      analyticsApi.getDiscipline(),
      analyticsApi.getMonthlyDaysChart()
    ])
    
    updateDailyWidgets(statsRes, presenceRes, attendanceResFirst, dailyRes)
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

onMounted(() => { loadDashboardData() })
</script>

<style scoped>
.dashboard-container { display: flex; flex-direction: column; gap: 1.5rem; padding-bottom: 2rem;}
.header-section { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
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
.charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }

.chart-card { background: #ffffff; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; }
.chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem; }
.chart-card h3 { font-size: 1.1rem; margin: 0; color: #0f172a; }

.header-controls { display: flex; gap: 0.5rem; }

.date-picker-input {
  padding: 0.35rem 0.6rem;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  font-size: 0.85rem;
  color: #475569;
  font-family: inherit;
  background: #f8fafc;
  cursor: pointer;
  outline: none;
  transition: border-color 0.2s;
}
.date-picker-input:focus { border-color: #3b82f6; }

.global-input {
  padding: 0.5rem 1rem;
  font-size: 1rem;
  font-weight: 600;
  color: #0f172a;
  border-color: #e2e8f0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.dept-select {
  min-width: 160px;
}

.chart-hint { font-size: 0.85rem; color: #64748b; margin: 0 0 1rem 0; display: flex; align-items: center; }
.legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; }
.legend-dot.green { background: #10b981; }
.legend-dot.red { background: #ef4444; margin-left: 15px; }

.scrollable-chart-container {
  max-height: 350px;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 8px;
}
.scrollable-chart-container::-webkit-scrollbar { width: 6px; }
.scrollable-chart-container::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 4px; }
.scrollable-chart-container::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
.scrollable-chart-container::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

.empty-chart { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; color: #94a3b8; }

.chart-element { height: 300px; width: 100%; }
.full-width-chart { grid-column: 1 / -1; margin-top: 0; }

@media (max-width: 1200px) {
  .charts-grid-half, .charts-grid { grid-template-columns: 1fr; }
  .header-section { flex-direction: column; align-items: flex-start; gap: 1rem; }
}
</style>