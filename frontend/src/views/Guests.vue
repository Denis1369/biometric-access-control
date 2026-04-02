<template>
  <div class="page-container">
    <div class="header-actions">
      <div>
        <h1 class="page-title">Гостевые пропуска</h1>
        <p class="page-subtitle">Выдача временных пропусков и фото-фиксация посетителей с камер проходной.</p>
      </div>
      <button class="btn-primary" @click="openNewDialog">
        <i class="pi pi-plus"></i> Выдать пропуск
      </button>
    </div>

    <div class="filters-bar">
      <div class="search-box">
        <i class="pi pi-search"></i>
        <input type="text" v-model="searchQuery" placeholder="Поиск по ФИО или цели визита..." />
      </div>

      <select v-model="selectedStatus" class="filter-select">
        <option value="all">Все статусы</option>
        <option value="active">Только активные</option>
        <option value="expired">Истекшие / Закрытые</option>
      </select>

      <select v-model="sortBy" class="filter-select">
        <option value="newest">Сначала новые</option>
        <option value="oldest">Сначала старые</option>
        <option value="name">По алфавиту (ФИО)</option>
      </select>
    </div>

    <div class="cards-grid">
      <div v-for="guest in filteredGuests" :key="guest.id" class="employee-card">
        <div class="card-header">
          <div class="status-badge" :class="isPassValid(guest.valid_until, guest.is_active) ? 'active' : 'blocked'">
            {{ isPassValid(guest.valid_until, guest.is_active) ? 'ПРОПУСК АКТИВЕН' : 'ИСТЕК / ЗАКРЫТ' }}
          </div>
          <div class="card-actions">
            <button 
              v-if="isPassValid(guest.valid_until, guest.is_active)" 
              class="btn-icon warning" 
              @click="deactivateGuest(guest.id)" 
              title="Аннулировать пропуск"
            >
              <i class="pi pi-ban"></i>
            </button>
          </div>
        </div>

        <div class="card-body">
          <div class="avatar-container">
            <img v-if="guest.photo_id" :src="guestsApi.getGuestPhotoUrl(guest.photo_id)" alt="Фото гостя" class="avatar-img" />
            <div v-else class="avatar-placeholder">
              <i class="pi pi-user"></i>
            </div>
          </div>
          
          <h3 class="emp-name">{{ guest.last_name }} {{ guest.first_name }}</h3>
          <p class="emp-middle-name">{{ guest.middle_name || ' ' }}</p>
          
          <div class="guest-info">
            <div class="info-row">
              <i class="pi pi-briefcase"></i> <span>{{ guest.purpose || 'Без цели' }}</span>
            </div>
            <div class="info-row" :class="{ 'expired': !isPassValid(guest.valid_until, guest.is_active) }">
              <i class="pi pi-clock"></i> <span>До: {{ formatDate(guest.valid_until) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="filteredGuests.length === 0" class="empty-state">
        <i class="pi pi-id-card empty-icon"></i>
        <h3>Нет подходящих пропусков</h3>
        <p>По вашему запросу ничего не найдено или список пуст.</p>
      </div>
    </div>

    <div v-if="displayDialog" class="modal-overlay" @click.self="closeDialog">
      <div class="modal-content wide-modal">
        <div class="modal-header">
          <h2>Оформление гостевого пропуска</h2>
          <button class="btn-icon close-btn" @click="closeDialog">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="modal-body-split">
          <div class="photo-column">
            <div class="avatar-preview">
              <img v-if="photoPreview" :src="photoPreview" class="avatar-img large" />
              <div v-else class="avatar-placeholder large">
                <i class="pi pi-camera"></i>
              </div>
            </div>

            <div class="capture-controls">
              <label class="control-label">Камера проходной:</label>
              <select v-model="selectedCameraId" class="form-input">
                <option value="" disabled>Выберите камеру...</option>
                <option v-for="cam in activeCameras" :key="cam.id" :value="cam.id">
                  {{ cam.name }}
                </option>
              </select>
              
              <button class="btn-primary full-width-btn" @click="takeSnapshot" :disabled="!selectedCameraId || isTakingSnapshot">
                <i class="pi" :class="isTakingSnapshot ? 'pi-spin pi-spinner' : 'pi-camera'"></i> 
                Сделать снимок
              </button>
              
              <div class="divider"><span>ИЛИ</span></div>
              
              <button class="btn-text upload-btn full-width-btn" @click="$refs.fileInput.click()">
                <i class="pi pi-upload"></i> Загрузить с ПК
              </button>
              <input type="file" accept="image/*" ref="fileInput" class="hidden-input" @change="onFileSelected" />
            </div>
          </div>

          <div class="form-column">
            <div class="form-grid">
              <div class="form-group">
                <label>Фамилия <span class="required">*</span></label>
                <input v-model="guestForm.last_name" type="text" class="form-input" />
              </div>
              
              <div class="form-group">
                <label>Имя <span class="required">*</span></label>
                <input v-model="guestForm.first_name" type="text" class="form-input" />
              </div>

              <div class="form-group">
                <label>Отчество</label>
                <input v-model="guestForm.middle_name" type="text" class="form-input" />
              </div>

              <div class="form-group">
                <label>Срок действия до <span class="required">*</span></label>
                <input v-model="guestForm.valid_until" type="datetime-local" class="form-input" />
              </div>

              <div class="form-group full-width">
                <label>Цель визита / К кому направляется</label>
                <input v-model="guestForm.purpose" type="text" class="form-input" placeholder="Например: Собеседование в IT-отдел" />
              </div>
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-text" @click="closeDialog">Отмена</button>
          <button class="btn-primary" @click="saveGuest">Выдать пропуск</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { guestsApi } from '../api/guests'
import { camerasApi } from '../api/cameras'

const guests = ref([])
const cameras = ref([])

// Новые переменные для фильтров
const searchQuery = ref('')
const selectedStatus = ref('active') // По умолчанию показываем активных
const sortBy = ref('newest')

const displayDialog = ref(false)
const isTakingSnapshot = ref(false)
const selectedCameraId = ref('')

const fileInput = ref(null)
const photoPreview = ref(null)

const guestForm = ref({
  last_name: '',
  first_name: '',
  middle_name: '',
  purpose: '',
  valid_until: '',
  photoFile: null
})

const loadData = async () => {
  try {
    const camerasRes = await camerasApi.getCameras()
    cameras.value = camerasRes.data
  } catch (error) {
    console.error('Ошибка загрузки камер:', error)
  }

  try {
    const guestsRes = await guestsApi.getGuests()
    guests.value = guestsRes.data
  } catch (error) {
    console.error('Ошибка загрузки гостей:', error)
  }
}

const activeCameras = computed(() => {
  return cameras.value.filter(c => c.is_active)
})

// === ОБНОВЛЕННАЯ ЛОГИКА ФИЛЬТРАЦИИ И СОРТИРОВКИ ===
const filteredGuests = computed(() => {
  // 1. Сначала фильтруем
  let result = guests.value.filter(g => {
    const query = searchQuery.value.toLowerCase()
    const fullName = `${g.last_name} ${g.first_name} ${g.middle_name || ''}`.toLowerCase()
    const purpose = (g.purpose || '').toLowerCase()
    const matchesSearch = fullName.includes(query) || purpose.includes(query)

    const isValid = isPassValid(g.valid_until, g.is_active)
    
    let matchesStatus = true
    if (selectedStatus.value === 'active') matchesStatus = isValid
    if (selectedStatus.value === 'expired') matchesStatus = !isValid

    return matchesSearch && matchesStatus
  })

  // 2. Затем сортируем
  result.sort((a, b) => {
    if (sortBy.value === 'newest') {
      return b.id - a.id // Сортируем по ID (самые новые сверху)
    } else if (sortBy.value === 'oldest') {
      return a.id - b.id
    } else if (sortBy.value === 'name') {
      const nameA = `${a.last_name} ${a.first_name}`.toLowerCase()
      const nameB = `${b.last_name} ${b.first_name}`.toLowerCase()
      return nameA.localeCompare(nameB)
    }
    return 0
  })

  return result
})

// Проверка срока годности: дата должна быть в будущем И пропуск не должен быть принудительно аннулирован
const isPassValid = (dateString, isActive) => {
  if (isActive === false) return false
  return new Date(dateString) > new Date()
}

const formatDate = (dateString) => {
  // Исправляем смещение UTC
  const d = new Date(dateString + 'Z')
  return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const onFileSelected = (event) => {
  const file = event.target.files[0]
  if (file) {
    guestForm.value.photoFile = file
    photoPreview.value = URL.createObjectURL(file)
  }
}

const takeSnapshot = async () => {
  if (!selectedCameraId.value) return
  isTakingSnapshot.value = true
  try {
    const res = await camerasApi.getSnapshot(selectedCameraId.value)
    const blob = res.data
    const file = new File([blob], "snapshot.jpg", { type: "image/jpeg" })
    guestForm.value.photoFile = file
    
    if (photoPreview.value) URL.revokeObjectURL(photoPreview.value)
    photoPreview.value = URL.createObjectURL(blob)
  } catch (error) {
    alert('Не удалось сделать снимок. Камера недоступна или в кадре нет людей.')
  } finally {
    isTakingSnapshot.value = false
  }
}

const openNewDialog = () => {
  photoPreview.value = null
  if (fileInput.value) fileInput.value.value = ''
  
  const today = new Date()
  today.setHours(23, 59, 0, 0)
  const tzOffset = (new Date()).getTimezoneOffset() * 60000;
  const localISOTime = (new Date(today - tzOffset)).toISOString().slice(0, 16);

  guestForm.value = { 
    last_name: '', first_name: '', middle_name: '', purpose: '',
    valid_until: localISOTime,
    photoFile: null 
  }
  displayDialog.value = true
}

const closeDialog = () => {
  displayDialog.value = false
  if (photoPreview.value) URL.revokeObjectURL(photoPreview.value)
}

const saveGuest = async () => {
  if (!guestForm.value.last_name || !guestForm.value.first_name || !guestForm.value.valid_until) {
    alert('Заполните обязательные поля (Фамилия, Имя, Срок действия)')
    return
  }
  if (!guestForm.value.photoFile) {
    alert('Сделайте снимок с камеры или загрузите фотографию гостя!')
    return
  }

  try {
    const formData = new FormData()
    formData.append('last_name', guestForm.value.last_name)
    formData.append('first_name', guestForm.value.first_name)
    if (guestForm.value.middle_name) formData.append('middle_name', guestForm.value.middle_name)
    if (guestForm.value.purpose) formData.append('purpose', guestForm.value.purpose)
    
    const validDate = new Date(guestForm.value.valid_until)
    formData.append('valid_until', validDate.toISOString())
    
    formData.append('photo', guestForm.value.photoFile)

    await guestsApi.createGuest(formData)
    closeDialog()
    await loadData()
  } catch (error) {
    const errorMsg = error.response?.data?.detail || 'Ошибка сохранения гостя'
    alert(errorMsg)
  }
}

// === НОВАЯ ЛОГИКА АННУЛИРОВАНИЯ ===
const deactivateGuest = async (id) => {
  if (confirm('Аннулировать пропуск? Гость больше не сможет пройти через турникет.')) {
    try {
      await guestsApi.deactivateGuest(id)
      await loadData()
    } catch (error) {
      alert('Ошибка при закрытии пропуска.')
    }
  }
}

onMounted(() => {
  loadData()
})
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

/* Стили для селектов-фильтров */
.filter-select { padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid #cbd5e1; background: #f8fafc; color: #334155; font-size: 0.95rem; outline: none; min-width: 180px; cursor: pointer; }
.filter-select:focus { border-color: #3b82f6; }

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
.avatar-placeholder { width: 90px; height: 90px; border-radius: 50%; background: #f1f5f9; color: #94a3b8; display: flex; align-items: center; justify-content: center; font-size: 2.5rem; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
.avatar-placeholder.large { width: 130px; height: 130px; font-size: 3.5rem; }
.avatar-img { width: 90px; height: 90px; border-radius: 50%; object-fit: cover; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
.avatar-img.large { width: 130px; height: 130px; }

.emp-name { margin: 0 0 0.25rem 0; color: #0f172a; font-size: 1.15rem; font-weight: 700; }
.emp-middle-name { margin: 0 0 1rem 0; color: #64748b; font-size: 0.9rem; min-height: 1.2rem; }

.guest-info { width: 100%; display: flex; flex-direction: column; gap: 0.5rem; background: #f8fafc; padding: 0.75rem; border-radius: 8px; border: 1px solid #e2e8f0;}
.info-row { display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; color: #475569; font-weight: 500; text-align: left; }
.info-row i { color: #8b5cf6; font-size: 1rem; }
.info-row.expired { color: #ef4444; }
.info-row.expired i { color: #ef4444; }

.empty-state { grid-column: 1 / -1; display: flex; flex-direction: column; align-items: center; padding: 4rem 2rem; color: #94a3b8; background: #ffffff; border-radius: 16px; border: 1px dashed #cbd5e1; }
.empty-icon { font-size: 3rem; margin-bottom: 1rem; color: #cbd5e1; }
.empty-state h3 { color: #334155; margin: 0 0 0.5rem 0; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: white; padding: 2rem; border-radius: 16px; width: 100%; max-height: 90vh; overflow-y: auto; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25); }
.wide-modal { max-width: 850px; }

.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.modal-header h2 { margin: 0; font-size: 1.3rem; color: #0f172a; }

.modal-body-split { display: flex; gap: 2rem; align-items: flex-start; }

.photo-column { width: 280px; flex-shrink: 0; display: flex; flex-direction: column; gap: 1.5rem; background: #f8fafc; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; }
.form-column { flex: 1; }

.avatar-preview { display: flex; justify-content: center; margin-bottom: 0.5rem; }

.capture-controls { display: flex; flex-direction: column; gap: 0.75rem; }
.control-label { font-size: 0.85rem; font-weight: 600; color: #475569; }

.divider { display: flex; align-items: center; text-align: center; color: #94a3b8; font-size: 0.8rem; margin: 0.5rem 0; }
.divider::before, .divider::after { content: ''; flex: 1; border-bottom: 1px solid #cbd5e1; }
.divider span { padding: 0 0.5rem; }

.full-width-btn { width: 100%; justify-content: center; }
.upload-btn { border: 1px dashed #cbd5e1; }
.hidden-input { display: none; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
.form-group { display: flex; flex-direction: column; gap: 0.4rem; }
.form-group.full-width { grid-column: 1 / -1; }
.form-group label { font-size: 0.85rem; font-weight: 600; color: #475569; }
.required { color: #ef4444; }
.form-input { width: 100%; box-sizing: border-box; padding: 0.75rem 1rem; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 0.95rem; background: #ffffff; outline: none; }
.form-input:focus { border-color: #3b82f6; }

.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 2rem; border-top: 1px solid #e2e8f0; padding-top: 1.5rem; }

.btn-primary, .btn-text { border: none; padding: 0.65rem 1.2rem; border-radius: 8px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; transition: 0.2s; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-primary:disabled { background: #94a3b8; cursor: not-allowed; }
.btn-text { background: transparent; color: #64748b; }
.btn-text:hover { background: #f1f5f9; color: #0f172a; }

.btn-icon { background: transparent; border: none; cursor: pointer; width: 32px; height: 32px; border-radius: 6px; color: #64748b; display: flex; align-items: center; justify-content: center; transition: 0.2s; }
.btn-icon:hover { background: #f1f5f9; color: #0f172a; }
.btn-icon.danger:hover { background: #fee2e2; color: #ef4444; }
.btn-icon.warning:hover { background: #fef3c7; color: #f59e0b; }

@media (max-width: 768px) {
  .modal-body-split { flex-direction: column; }
  .photo-column { width: 100%; box-sizing: border-box; }
  .form-grid { grid-template-columns: 1fr; }
}
</style>