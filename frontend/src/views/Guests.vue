<template>
  <div class="page-container">
    <BasePageHeader
      title="Гостевые пропуска"
      subtitle="Выдача временных пропусков и фото-фиксация посетителей с камер проходной."
    >
      <template #actions>
        <BaseButton v-if="canIssueGuestPass" @click="openNewDialog">
          <i class="pi pi-plus"></i> Выдать пропуск
        </BaseButton>
      </template>
    </BasePageHeader>

    <GuestsFilters
      v-model:search-query="searchQuery"
      v-model:selected-status="selectedStatus"
      v-model:sort-by="sortBy"
    />

    <div class="cards-grid">
      <GuestCard
        v-for="guest in filteredGuests"
        :key="guest.id"
        :guest="guest"
        :photo-url="getGuestPhotoUrl(guest)"
        :pass-valid="isPassValid(guest.valid_until, guest.is_active)"
        :valid-until-label="formatDate(guest.valid_until)"
        :can-build-route="canBuildGuestRoutes"
        :can-add-body-photo="canAddGuestBodyPhoto"
        :can-deactivate="canDeactivateGuestPass"
        @build-route="openRouteDialog"
        @add-body-photo="openBodyPhotoDialog"
        @deactivate="deactivateGuest($event.id)"
      />

      <EmptyState
        v-if="filteredGuests.length === 0"
        class="guest-list-empty"
        icon="pi pi-id-card"
        title="Нет подходящих пропусков"
        description="По вашему запросу ничего не найдено или список пуст."
      />
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
            <div class="photo-upload-block">
              <label class="photo-block-title">Фото лица</label>
              <div class="avatar-preview">
                <img v-if="facePhotoPreview" :src="facePhotoPreview" class="avatar-img large" />
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
                  Сделать снимок лица
                </button>

                <div class="divider"><span>ИЛИ</span></div>

                <button class="btn-text upload-btn full-width-btn" @click="$refs.faceFileInput.click()">
                  <i class="pi pi-upload"></i> Загрузить фото лица
                </button>
                <input type="file" accept="image/*" ref="faceFileInput" class="hidden-input" @change="onFaceFileSelected" />
              </div>
            </div>

            <div class="photo-upload-block">
              <label class="photo-block-title">Фото полного роста для Re-ID</label>
              <div class="avatar-preview body-preview">
                <img v-if="bodyPhotoPreview" :src="bodyPhotoPreview" class="avatar-img large" />
                <div v-else class="avatar-placeholder large">
                  <i class="pi pi-id-card"></i>
                </div>
              </div>

              <button
                class="btn-primary full-width-btn"
                @click="takeBodySnapshot"
                :disabled="!selectedCameraId || isTakingBodySnapshot"
              >
                <i class="pi" :class="isTakingBodySnapshot ? 'pi-spin pi-spinner' : 'pi-camera'"></i>
                Сделать снимок полного роста
              </button>

              <div class="divider"><span>ИЛИ</span></div>

              <button class="btn-text upload-btn full-width-btn" @click="$refs.bodyFileInput.click()">
                <i class="pi pi-upload"></i> Загрузить полный рост
              </button>
              <input type="file" accept="image/*" ref="bodyFileInput" class="hidden-input" @change="onBodyFileSelected" />
              <p class="capture-hint">Это фото нужно, чтобы Re-ID отслеживал гостя по одежде и силуэту.</p>
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
                <label>К кому пришли <span class="required">*</span></label>
                <div class="employee-select">
                  <button type="button" class="form-input employee-select-trigger" @click="toggleEmployeeDropdown">
                    <span :class="{ 'placeholder-text': !selectedEmployeeName }">
                      {{ selectedEmployeeName || 'Выберите сотрудника...' }}
                    </span>
                    <i class="pi" :class="employeeDropdownOpen ? 'pi-chevron-up' : 'pi-chevron-down'"></i>
                  </button>

                  <div v-if="employeeDropdownOpen" class="employee-select-panel">
                    <div class="employee-search-box">
                      <i class="pi pi-search"></i>
                      <input
                        v-model="employeeSearchQuery"
                        type="text"
                        class="employee-search-input"
                        placeholder="Поиск по ФИО..."
                      />
                    </div>

                    <div class="employee-options-list">
                      <button
                        v-for="employee in filteredEmployeeOptions"
                        :key="employee.id"
                        type="button"
                        class="employee-option"
                        :class="{ selected: String(guestForm.employee_id) === String(employee.id) }"
                        @click="selectEmployee(employee)"
                      >
                        {{ getEmployeeFullName(employee) }}
                      </button>

                      <div v-if="filteredEmployeeOptions.length === 0" class="employee-option-empty">
                        Сотрудники не найдены
                      </div>
                    </div>
                  </div>
                </div>
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

    <div v-if="bodyPhotoDialogVisible" class="modal-overlay" @click.self="closeBodyPhotoDialog">
      <div class="modal-content small-modal">
        <div class="modal-header">
          <h2>Фото полного роста для Re-ID</h2>
          <button class="btn-icon close-btn" @click="closeBodyPhotoDialog">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <p class="capture-hint">
          Гость: {{ formatGuestName(bodyPhotoGuest) }}. Сделайте снимок с камеры или загрузите кадр, где человек виден в полный рост.
        </p>
        <div class="avatar-preview body-preview modal-preview">
          <img v-if="bodyEnrollmentPreview" :src="bodyEnrollmentPreview" class="avatar-img large" />
          <div v-else class="avatar-placeholder large">
            <i class="pi pi-id-card"></i>
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

          <button
            class="btn-primary full-width-btn"
            @click="takeBodyEnrollmentSnapshot"
            :disabled="!selectedCameraId || isTakingBodyEnrollmentSnapshot || bodyPhotoSaving"
          >
            <i class="pi" :class="isTakingBodyEnrollmentSnapshot ? 'pi-spin pi-spinner' : 'pi-camera'"></i>
            Сделать снимок полного роста
          </button>

          <div class="divider"><span>ИЛИ</span></div>
        </div>
        <button class="btn-text upload-btn full-width-btn" @click="$refs.bodyEnrollmentInput.click()">
          <i class="pi pi-upload"></i> Выбрать фото полного роста
        </button>
        <input type="file" accept="image/*" ref="bodyEnrollmentInput" class="hidden-input" @change="onBodyEnrollmentFileSelected" />

        <div class="modal-actions">
          <button class="btn-text" @click="closeBodyPhotoDialog">Отмена</button>
          <button class="btn-primary" :disabled="!bodyEnrollmentFile || bodyPhotoSaving" @click="saveGuestBodyPhoto">
            {{ bodyPhotoSaving ? 'Сохранение...' : 'Сохранить Re-ID фото' }}
          </button>
        </div>
      </div>
    </div>

    <GuestRouteModal
      v-model:open="routeDialogVisible"
      v-model:floor-id="routeFloorId"
      v-model:date-from="routeDateFrom"
      v-model:clock-from="routeClockFrom"
      v-model:date-to="routeDateTo"
      v-model:clock-to="routeClockTo"
      :guest="routeGuest"
      :floor-options="floorOptions"
      :job="routeJob"
      :job-loading="routeJobLoading"
      :result-loading="routeResultLoading"
      :result="routeResult"
      :can-build-from-journal="canBuildGuestRoutes"
      :can-start-analysis="canAnalyzeGuestRoutes"
      @close="closeRouteDialog"
      @floor-change="onRouteFloorChange"
      @build-from-journal="buildRouteFromJournal"
      @start-analysis="startGuestRouteAnalysis"
    />
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount, onMounted, computed } from 'vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BasePageHeader from '../components/ui/BasePageHeader.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import GuestCard from '../components/guests/GuestCard.vue'
import GuestRouteModal from '../components/guests/GuestRouteModal.vue'
import GuestsFilters from '../components/guests/GuestsFilters.vue'
import { buildingsApi } from '../api/buildings'
import { guestsApi } from '../api/guests'
import { camerasApi } from '../api/cameras'
import { employeesApi } from '../api/employees'
import { floorsApi } from '../api/floors'
import { guestRoutesApi } from '../api/guestRoutes'
import { PERMISSIONS } from '../constants/roles'
import { createJsonWebSocket } from '../services/jsonWebSocket'
import { useAuth } from '../services/auth'
import { useUi } from '../services/ui'

defineOptions({ name: 'GuestsPage' })

/**
 * Страница гостевых пропусков.
 *
 * Здесь оператор КПП оформляет временный пропуск гостю: вводит ФИО, выбирает
 * сопровождающего сотрудника, задаёт срок действия, загружает фото лица и при
 * необходимости фото полного роста. Фото лица нужно для распознавания на
 * проходной, а фото полного роста используется Re-ID модулем, чтобы позже
 * искать этого гостя на file-камерах этажа и строить вероятный маршрут.
 *
 * На этой же странице открывается `GuestRouteModal`: маршрут логически
 * относится к конкретному гостю, поэтому сценарий “построить маршрут” живёт
 * здесь, а не на технической странице плана здания.
 */
const auth = useAuth()
const ui = useUi()
const canIssueGuestPass = computed(() => (
  auth.hasPermission(PERMISSIONS.GUESTS_WRITE) &&
  auth.hasPermission(PERMISSIONS.GUEST_PASSES_ISSUE)
))
const canAddGuestBodyPhoto = computed(() => auth.hasPermission(PERMISSIONS.GUESTS_WRITE))
const canDeactivateGuestPass = computed(() => auth.hasPermission(PERMISSIONS.GUEST_PASSES_CLOSE))
const canBuildGuestRoutes = computed(() => auth.hasPermission(PERMISSIONS.GUEST_ROUTES_READ))
const canAnalyzeGuestRoutes = computed(() => (
  auth.hasPermission(PERMISSIONS.GUEST_ROUTES_ANALYZE_VIDEO) &&
  !auth.hasAnyRole('analyst', 'manager_analyst', 'checkpoint_operator')
))

const guests = ref([])
const cameras = ref([])
const employees = ref([])
const buildings = ref([])
const floors = ref([])

const searchQuery = ref('')
const selectedStatus = ref('active')
const sortBy = ref('newest')

const displayDialog = ref(false)
const isTakingSnapshot = ref(false)
const isTakingBodySnapshot = ref(false)
const selectedCameraId = ref('')
const employeeDropdownOpen = ref(false)
const employeeSearchQuery = ref('')

const faceFileInput = ref(null)
const bodyFileInput = ref(null)
const facePhotoPreview = ref(null)
const bodyPhotoPreview = ref(null)

const bodyPhotoDialogVisible = ref(false)
const bodyPhotoGuest = ref(null)
const bodyEnrollmentInput = ref(null)
const bodyEnrollmentFile = ref(null)
const bodyEnrollmentPreview = ref(null)
const bodyPhotoSaving = ref(false)
const isTakingBodyEnrollmentSnapshot = ref(false)

const routeDialogVisible = ref(false)
const routeGuest = ref(null)
const routeFloorId = ref('')
const routeJob = ref(null)
const routeJobLoading = ref(false)
const routeResultLoading = ref(false)
const routeResult = ref(null)
const routeDateFrom = ref('')
const routeClockFrom = ref('')
const routeDateTo = ref('')
const routeClockTo = ref('')
let routeJobSocket = null
let routeJobFinalized = false

const guestForm = ref({
  last_name: '',
  first_name: '',
  middle_name: '',
  employee_id: '',
  valid_until: '',
  facePhotoFile: null,
  bodyPhotoFile: null,
})

const parseLocalDate = (dateString) => {
  const parsed = new Date(dateString)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const loadData = async () => {
  try {
    const [camerasRes, guestsRes, employeesRes, buildingsRes, floorsRes] = await Promise.all([
      (canIssueGuestPass.value || canAddGuestBodyPhoto.value) ? camerasApi.getCameras() : Promise.resolve({ data: [] }),
      guestsApi.getGuests(),
      canIssueGuestPass.value ? employeesApi.getEmployees(0, 1000) : Promise.resolve({ data: [] }),
      canBuildGuestRoutes.value ? buildingsApi.getBuildings() : Promise.resolve({ data: [] }),
      canBuildGuestRoutes.value ? floorsApi.getFloors() : Promise.resolve({ data: [] }),
    ])

    cameras.value = camerasRes.data
    guests.value = guestsRes.data
    employees.value = employeesRes.data.filter(employee => employee.is_active)
    buildings.value = buildingsRes.data
    floors.value = floorsRes.data
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось загрузить данные для гостевых пропусков'))
  }
}

const activeCameras = computed(() => {
  return cameras.value.filter(camera => camera.is_active)
})

const getEmployeeFullName = (employee) => {
  return [employee.last_name, employee.first_name, employee.middle_name].filter(Boolean).join(' ')
}

const selectedEmployeeName = computed(() => {
  const employee = employees.value.find(item => String(item.id) === String(guestForm.value.employee_id))
  return employee ? getEmployeeFullName(employee) : ''
})

const floorOptions = computed(() => {
  const buildingById = new Map(buildings.value.map(building => [building.id, building]))
  return floors.value.map(floor => {
    const buildingName = buildingById.get(floor.building_id)?.name || `Здание ${floor.building_id}`
    return {
      ...floor,
      label: `${buildingName} · ${floor.name} (${floor.floor_number} этаж)`,
    }
  })
})

const filteredEmployeeOptions = computed(() => {
  const query = employeeSearchQuery.value.trim().toLowerCase()
  if (!query) return employees.value
  return employees.value.filter(employee => getEmployeeFullName(employee).toLowerCase().includes(query))
})

const filteredGuests = computed(() => {
  let result = guests.value.filter(guest => {
    const query = searchQuery.value.toLowerCase()
    const fullName = `${guest.last_name} ${guest.first_name} ${guest.middle_name || ''}`.toLowerCase()
    const employeeName = (guest.employee_name || '').toLowerCase()
    const matchesSearch = fullName.includes(query) || employeeName.includes(query)

    const isValid = isPassValid(guest.valid_until, guest.is_active)

    let matchesStatus = true
    if (selectedStatus.value === 'active') matchesStatus = isValid
    if (selectedStatus.value === 'expired') matchesStatus = !isValid

    return matchesSearch && matchesStatus
  })

  result.sort((a, b) => {
    if (sortBy.value === 'newest') return b.id - a.id
    if (sortBy.value === 'oldest') return a.id - b.id
    if (sortBy.value === 'name') {
      const nameA = `${a.last_name} ${a.first_name}`.toLowerCase()
      const nameB = `${b.last_name} ${b.first_name}`.toLowerCase()
      return nameA.localeCompare(nameB)
    }
    return 0
  })

  return result
})

const isPassValid = (dateString, isActive) => {
  if (isActive === false) return false
  const parsed = parseLocalDate(dateString)
  return parsed ? parsed > new Date() : false
}

const formatDate = (dateString) => {
  const d = parseLocalDate(dateString)
  if (!d) return 'Некорректная дата'
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const getGuestPhotoUrl = (guest) => (guest.photo_id ? guestsApi.getGuestPhotoUrl(guest.photo_id) : '')

const toggleEmployeeDropdown = () => {
  employeeDropdownOpen.value = !employeeDropdownOpen.value
  if (!employeeDropdownOpen.value) employeeSearchQuery.value = ''
}

const selectEmployee = (employee) => {
  guestForm.value.employee_id = String(employee.id)
  employeeDropdownOpen.value = false
  employeeSearchQuery.value = ''
}

const formatGuestName = (guest) => {
  if (!guest) return ''
  return [guest.last_name, guest.first_name, guest.middle_name].filter(Boolean).join(' ')
}

const revokePreview = (previewRef) => {
  if (previewRef.value) {
    URL.revokeObjectURL(previewRef.value)
    previewRef.value = null
  }
}

const onFaceFileSelected = (event) => {
  const file = event.target.files[0]
  if (file) {
    guestForm.value.facePhotoFile = file
    revokePreview(facePhotoPreview)
    facePhotoPreview.value = URL.createObjectURL(file)
  }
}

const onBodyFileSelected = (event) => {
  const file = event.target.files[0]
  if (file) {
    guestForm.value.bodyPhotoFile = file
    revokePreview(bodyPhotoPreview)
    bodyPhotoPreview.value = URL.createObjectURL(file)
  }
}

const takeSnapshot = async () => {
  if (!selectedCameraId.value) return
  isTakingSnapshot.value = true
  try {
    const res = await camerasApi.getSnapshot(selectedCameraId.value)
    const blob = res.data
    const file = new File([blob], 'face_snapshot.jpg', { type: 'image/jpeg' })
    guestForm.value.facePhotoFile = file

    revokePreview(facePhotoPreview)
    facePhotoPreview.value = URL.createObjectURL(blob)
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось сделать снимок. Камера недоступна или в кадре нет людей.'))
  } finally {
    isTakingSnapshot.value = false
  }
}

/**
 * Получить кадр с выбранной камеры и использовать его как фото полного роста.
 *
 * Backend отдаёт обычный JPEG snapshot последнего кадра камеры. Для Re-ID нам
 * важно не то, откуда пришла картинка, а чтобы на ней человек был виден в
 * полный рост. Поэтому тот же snapshot можно сохранить как body_photo и
 * отправить в endpoint гостя так же, как файл, выбранный вручную.
 */
const captureBodyPhotoFromCamera = async ({ assignFile, previewRef, fileName, setLoading }) => {
  if (!selectedCameraId.value) return
  setLoading(true)
  try {
    const res = await camerasApi.getSnapshot(selectedCameraId.value)
    const blob = res.data
    const file = new File([blob], fileName, { type: 'image/jpeg' })
    assignFile(file)

    revokePreview(previewRef)
    previewRef.value = URL.createObjectURL(blob)
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось сделать снимок полного роста. Проверьте камеру и положение человека в кадре.'))
  } finally {
    setLoading(false)
  }
}

const takeBodySnapshot = () => captureBodyPhotoFromCamera({
  assignFile: (file) => {
    guestForm.value.bodyPhotoFile = file
  },
  previewRef: bodyPhotoPreview,
  fileName: 'body_snapshot.jpg',
  setLoading: (value) => {
    isTakingBodySnapshot.value = value
  },
})

const takeBodyEnrollmentSnapshot = () => captureBodyPhotoFromCamera({
  assignFile: (file) => {
    bodyEnrollmentFile.value = file
  },
  previewRef: bodyEnrollmentPreview,
  fileName: 'body_enrollment_snapshot.jpg',
  setLoading: (value) => {
    isTakingBodyEnrollmentSnapshot.value = value
  },
})

const openNewDialog = () => {
  if (!canIssueGuestPass.value) return
  revokePreview(facePhotoPreview)
  revokePreview(bodyPhotoPreview)
  if (faceFileInput.value) faceFileInput.value.value = ''
  if (bodyFileInput.value) bodyFileInput.value.value = ''

  const today = new Date()
  today.setHours(23, 59, 0, 0)
  const tzOffset = new Date().getTimezoneOffset() * 60000
  const localISOTime = new Date(today - tzOffset).toISOString().slice(0, 16)

  guestForm.value = {
    last_name: '',
    first_name: '',
    middle_name: '',
    employee_id: '',
    valid_until: localISOTime,
    facePhotoFile: null,
    bodyPhotoFile: null,
  }
  employeeDropdownOpen.value = false
  employeeSearchQuery.value = ''
  displayDialog.value = true
}

const closeDialog = () => {
  displayDialog.value = false
  employeeDropdownOpen.value = false
  employeeSearchQuery.value = ''
  revokePreview(facePhotoPreview)
  revokePreview(bodyPhotoPreview)
}

const saveGuest = async () => {
  if (!canIssueGuestPass.value) return
  if (!guestForm.value.last_name || !guestForm.value.first_name || !guestForm.value.valid_until || !guestForm.value.employee_id) {
    ui.warn('Заполните обязательные поля: фамилия, имя, к кому пришли и срок действия')
    return
  }
  if (!guestForm.value.facePhotoFile) {
    ui.warn('Сделайте снимок лица с камеры или загрузите фото лица гостя.')
    return
  }

  try {
    const formData = new FormData()
    formData.append('last_name', guestForm.value.last_name)
    formData.append('first_name', guestForm.value.first_name)
    if (guestForm.value.middle_name) formData.append('middle_name', guestForm.value.middle_name)
    formData.append('employee_id', guestForm.value.employee_id)

    formData.append('valid_until', guestForm.value.valid_until)
    formData.append('face_photo', guestForm.value.facePhotoFile)
    if (guestForm.value.bodyPhotoFile) formData.append('body_photo', guestForm.value.bodyPhotoFile)

    await guestsApi.createGuest(formData)
    closeDialog()
    await loadData()
    ui.success('Гостевой пропуск выдан')
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Ошибка сохранения гостя'))
  }
}

const openBodyPhotoDialog = (guest) => {
  if (!canAddGuestBodyPhoto.value) return
  bodyPhotoGuest.value = guest
  bodyEnrollmentFile.value = null
  revokePreview(bodyEnrollmentPreview)
  if (bodyEnrollmentInput.value) bodyEnrollmentInput.value.value = ''
  bodyPhotoDialogVisible.value = true
}

const closeBodyPhotoDialog = () => {
  bodyPhotoDialogVisible.value = false
  bodyPhotoGuest.value = null
  bodyEnrollmentFile.value = null
  revokePreview(bodyEnrollmentPreview)
}

const onBodyEnrollmentFileSelected = (event) => {
  const file = event.target.files[0]
  if (!file) return
  bodyEnrollmentFile.value = file
  revokePreview(bodyEnrollmentPreview)
  bodyEnrollmentPreview.value = URL.createObjectURL(file)
}

const saveGuestBodyPhoto = async () => {
  if (!canAddGuestBodyPhoto.value) return
  if (!bodyPhotoGuest.value || !bodyEnrollmentFile.value) return
  bodyPhotoSaving.value = true
  try {
    const formData = new FormData()
    formData.append('body_photo', bodyEnrollmentFile.value)
    await guestsApi.uploadBodyPhoto(bodyPhotoGuest.value.id, formData)
    closeBodyPhotoDialog()
    await loadData()
    ui.success('Фото полного роста сохранено, Re-ID активен')
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Не удалось сохранить фото полного роста'))
  } finally {
    bodyPhotoSaving.value = false
  }
}

const toDateTimeLocalValue = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 16)
  const offsetMs = date.getTimezoneOffset() * 60000
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16)
}

const splitDateTimeLocalValue = (value) => {
  const normalized = toDateTimeLocalValue(value)
  return {
    date: normalized.slice(0, 10),
    time: normalized.slice(11, 16),
  }
}

const combineRouteDateTime = (dateValue, timeValue, fallbackTime) => {
  if (!dateValue) return ''
  return `${dateValue}T${timeValue || fallbackTime}`
}

const getRoutePeriodParams = () => ({
  time_from: combineRouteDateTime(routeDateFrom.value, routeClockFrom.value, '00:00'),
  time_to: combineRouteDateTime(routeDateTo.value, routeClockTo.value, '23:59'),
})

const setDefaultRoutePeriod = () => {
  const now = new Date()
  const from = new Date(now.getTime() - 24 * 60 * 60 * 1000)
  const fromParts = splitDateTimeLocalValue(from)
  const toParts = splitDateTimeLocalValue(now)
  routeDateFrom.value = fromParts.date
  routeClockFrom.value = fromParts.time
  routeDateTo.value = toParts.date
  routeClockTo.value = toParts.time
}

const onRouteFloorChange = () => {
  routeResult.value = null
  routeJob.value = null
}

const clearRouteJobSubscription = () => {
  if (routeJobSocket) {
    routeJobSocket.close()
    routeJobSocket = null
  }
}

const openRouteDialog = (guest) => {
  if (!canBuildGuestRoutes.value) return
  routeGuest.value = guest
  routeJob.value = null
  routeResult.value = null
  routeResultLoading.value = false
  routeJobFinalized = false
  setDefaultRoutePeriod()
  routeFloorId.value = floorOptions.value[0]?.id ? String(floorOptions.value[0].id) : ''
  routeDialogVisible.value = true
}

const closeRouteDialog = () => {
  clearRouteJobSubscription()
  routeDialogVisible.value = false
  routeGuest.value = null
  routeJob.value = null
  routeJobLoading.value = false
  routeResultLoading.value = false
  routeResult.value = null
  routeJobFinalized = false
}

const buildRouteFromJournal = async () => {
  if (!canBuildGuestRoutes.value) return
  if (!routeGuest.value || !routeFloorId.value) return
  routeResultLoading.value = true
  try {
    const response = await guestRoutesApi.getGuestProbableRoute(routeFloorId.value, routeGuest.value.id, {
      ...getRoutePeriodParams(),
    })
    routeResult.value = response.data

    if (!response.data.events?.length) {
      ui.warn('За выбранный период событий не найдено')
    } else if ((response.data.warnings || []).length) {
      ui.warn('Маршрут построен с предупреждениями')
    } else {
      ui.success('Вероятный маршрут гостя построен')
    }
  } catch (error) {
    routeResult.value = null
    ui.error(ui.getErrorMessage(error, 'Не удалось построить маршрут гостя'))
  } finally {
    routeResultLoading.value = false
  }
}

const buildRouteForCompletedJob = async (job) => {
  routeFloorId.value = String(job.floor_id)
  const fromParts = splitDateTimeLocalValue(job.started_at)
  const toParts = splitDateTimeLocalValue(job.finished_at)
  routeDateFrom.value = fromParts.date
  routeClockFrom.value = fromParts.time
  routeDateTo.value = toParts.date
  routeClockTo.value = toParts.time

  if (job.probable_route) {
    routeResult.value = job.probable_route
    if (!job.probable_route.events?.length) {
      ui.warn('За выбранный период событий не найдено')
    } else if ((job.warnings || []).length) {
      ui.warn('Маршрут построен с предупреждениями')
    } else {
      ui.success('Видео проанализировано, маршрут построен')
    }
    return
  }

  await buildRouteFromJournal()
}

const handleRouteJobUpdate = async (job) => {
  routeJob.value = job

  if (job.status === 'completed' && !routeJobFinalized) {
    routeJobFinalized = true
    clearRouteJobSubscription()
    routeJobLoading.value = false
    await buildRouteForCompletedJob(job)
  } else if (job.status === 'failed' && !routeJobFinalized) {
    routeJobFinalized = true
    clearRouteJobSubscription()
    routeJobLoading.value = false
    ui.error(job.error_message || 'Офлайн-анализ маршрута завершился с ошибкой')
  }
}

const subscribeRouteJob = (jobId) => {
  clearRouteJobSubscription()
  routeJobFinalized = false
  routeJobSocket = createJsonWebSocket({
    path: `/ws/guest-route-analysis-jobs/${jobId}`,
    onMessage: (job) => {
      void handleRouteJobUpdate(job)
    },
    onError: (error) => {
      if (!routeJobFinalized) {
        routeJobLoading.value = false
        ui.error(ui.getErrorMessage(error, 'WebSocket статуса маршрута недоступен'))
      }
    },
  })
}

const startGuestRouteAnalysis = async () => {
  if (!canAnalyzeGuestRoutes.value) return
  if (!routeGuest.value || !routeFloorId.value) return
  if (!routeGuest.value.has_body_embedding) {
    ui.warn('Для анализа видео добавьте гостю фото полного роста для Re-ID')
    return
  }
  routeJobLoading.value = true
  routeJob.value = null
  routeResult.value = null
  clearRouteJobSubscription()
  try {
    const response = await guestRoutesApi.createGuestRouteAnalysisJob(routeFloorId.value, routeGuest.value.id)
    routeJob.value = response.data
    subscribeRouteJob(response.data.id)
  } catch (error) {
    routeJobLoading.value = false
    ui.error(ui.getErrorMessage(error, 'Не удалось запустить анализ маршрута гостя'))
  }
}

const deactivateGuest = async (id) => {
  if (!canDeactivateGuestPass.value) return
  const accepted = await ui.confirm({
    header: 'Аннулировать пропуск?',
    message: 'Гость больше не сможет пройти через турникет.',
    acceptLabel: 'Аннулировать',
    acceptSeverity: 'danger',
  })
  if (!accepted) return

  try {
    await guestsApi.deactivateGuest(id)
    await loadData()
    ui.success('Гостевой пропуск аннулирован')
  } catch (error) {
    ui.error(ui.getErrorMessage(error, 'Ошибка при закрытии пропуска'))
  }
}

onMounted(() => {
  loadData()
})

onBeforeUnmount(() => {
  clearRouteJobSubscription()
  revokePreview(facePhotoPreview)
  revokePreview(bodyPhotoPreview)
  revokePreview(bodyEnrollmentPreview)
})
</script>

<style scoped>
.page-container { background: transparent; height: 100%; display: flex; flex-direction: column; gap: 1.5rem; }
.cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.5rem; }
.guest-list-empty { grid-column: 1 / -1; background: #ffffff; border: 1px dashed #cbd5e1; border-radius: 16px; }
.avatar-placeholder { width: 90px; height: 90px; border-radius: 50%; background: #f1f5f9; color: #94a3b8; display: flex; align-items: center; justify-content: center; font-size: 2.5rem; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
.avatar-placeholder.large { width: 130px; height: 130px; font-size: 3.5rem; }
.avatar-img { width: 90px; height: 90px; border-radius: 50%; object-fit: cover; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
.avatar-img.large { width: 130px; height: 130px; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: white; padding: 2rem; border-radius: 16px; width: 100%; max-height: 90vh; overflow-y: auto; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25); }
.wide-modal { max-width: 850px; }

.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.modal-header h2 { margin: 0; font-size: 1.3rem; color: #0f172a; }

.modal-body-split { display: flex; gap: 2rem; align-items: flex-start; }

.photo-column { width: 280px; flex-shrink: 0; display: flex; flex-direction: column; gap: 1rem; background: #f8fafc; padding: 1.5rem; border-radius: 12px; border: 1px solid #e2e8f0; }
.form-column { flex: 1; }

.photo-upload-block { display: flex; flex-direction: column; gap: 0.75rem; padding: 0.9rem; border-radius: 12px; background: #ffffff; border: 1px solid #e2e8f0; }
.photo-block-title { color: #334155; font-size: 0.9rem; font-weight: 700; }
.avatar-preview { display: flex; justify-content: center; margin-bottom: 0.5rem; }
.body-preview .avatar-img,
.body-preview .avatar-placeholder { border-radius: 16px; }
.modal-preview { width: 220px; margin: 1rem auto; }

.capture-controls { display: flex; flex-direction: column; gap: 0.75rem; }
.control-label { font-size: 0.85rem; font-weight: 600; color: #475569; }

.divider { display: flex; align-items: center; text-align: center; color: #94a3b8; font-size: 0.8rem; margin: 0.5rem 0; }
.divider::before, .divider::after { content: ''; flex: 1; border-bottom: 1px solid #cbd5e1; }
.divider span { padding: 0 0.5rem; }

.full-width-btn { width: 100%; justify-content: center; }
.upload-btn { border: 1px dashed #cbd5e1; }
.hidden-input { display: none; }
.capture-hint { margin: 0; color: #64748b; font-size: 0.8rem; line-height: 1.35; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
.form-group { display: flex; flex-direction: column; gap: 0.4rem; }
.form-group.full-width { grid-column: 1 / -1; }
.form-group label { font-size: 0.85rem; font-weight: 600; color: #475569; }
.required { color: #ef4444; }
.form-input { width: 100%; box-sizing: border-box; padding: 0.75rem 1rem; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 0.95rem; background: #ffffff; outline: none; }
.form-input:focus { border-color: #3b82f6; }
.placeholder-text { color: #94a3b8; }

.employee-select {
  position: relative;
}

.employee-select-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  text-align: left;
}

.employee-select-panel {
  position: absolute;
  top: calc(100% + 0.5rem);
  left: 0;
  right: 0;
  z-index: 20;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.12);
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  max-height: min(200px, 45vh);
  overflow: hidden;
}

.employee-search-box {
  position: relative;
  margin-bottom: 0.75rem;
  flex-shrink: 0;
}

.employee-search-box i {
  position: absolute;
  left: 0.85rem;
  top: 50%;
  transform: translateY(-50%);
  color: #94a3b8;
}

.employee-search-input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.7rem 0.9rem 0.7rem 2.4rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.92rem;
  outline: none;
}

.employee-search-input:focus {
  border-color: #3b82f6;
}

.employee-options-list {
  overflow-y: auto;
  min-height: 0;
  padding-right: 0.25rem;
}

.employee-option {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  padding: 0.7rem 0.85rem;
  border-radius: 8px;
  cursor: pointer;
  color: #334155;
  font-size: 0.94rem;
}

.employee-option:hover,
.employee-option.selected {
  background: #eff6ff;
  color: #1d4ed8;
}

.employee-option-empty {
  padding: 0.7rem 0.85rem;
  color: #94a3b8;
  font-size: 0.9rem;
}
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
