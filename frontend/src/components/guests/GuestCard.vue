<template>
  <article class="guest-card">
    <header class="guest-card__header">
      <StatusBadge :tone="passValid ? 'success' : 'danger'">
        {{ passValid ? 'ПРОПУСК АКТИВЕН' : 'ИСТЕК / ЗАКРЫТ' }}
      </StatusBadge>

      <div v-if="canBuildRoute || canAddBodyPhoto || canDeactivate" class="guest-card__actions">
        <BaseIconButton
          v-if="canBuildRoute"
          icon="pi pi-map-marker"
          label="Построить маршрут гостя"
          @click="$emit('build-route', guest)"
        />
        <BaseIconButton
          v-if="canAddBodyPhoto && !guest.has_body_embedding"
          icon="pi pi-id-card"
          label="Добавить фото полного роста для Re-ID"
          @click="$emit('add-body-photo', guest)"
        />
        <BaseIconButton
          v-if="canDeactivate && passValid"
          icon="pi pi-ban"
          label="Аннулировать пропуск"
          tone="warning"
          @click="$emit('deactivate', guest)"
        />
      </div>
    </header>

    <div class="guest-card__body">
      <div class="guest-card__avatar">
        <img
          v-if="photoUrl"
          :src="photoUrl"
          alt="Фото гостя"
          class="guest-card__avatar-image"
        />
        <div v-else class="guest-card__avatar-placeholder">
          <i class="pi" :class="guest.has_body_embedding ? 'pi-id-card' : 'pi-user'"></i>
        </div>
      </div>

      <h3 class="guest-card__name">{{ guest.last_name }} {{ guest.first_name }}</h3>
      <p class="guest-card__middle-name">{{ guest.middle_name || ' ' }}</p>

      <div class="guest-card__info">
        <div class="guest-card__info-row">
          <i class="pi pi-user"></i>
          <span>{{ guest.employee_name || 'Сотрудник не указан' }}</span>
        </div>
        <div class="guest-card__info-row" :class="{ 'guest-card__info-row--expired': !passValid }">
          <i class="pi pi-clock"></i>
          <span>До: {{ validUntilLabel }}</span>
        </div>
        <div v-if="guest.has_body_embedding" class="guest-card__info-row guest-card__info-row--reid">
          <i class="pi pi-eye"></i>
          <span>Re-ID по силуэту активен</span>
        </div>
      </div>
    </div>
  </article>
</template>

<script setup>
import BaseIconButton from '../ui/BaseIconButton.vue'
import StatusBadge from '../ui/StatusBadge.vue'

defineProps({
  guest: {
    type: Object,
    required: true,
  },
  photoUrl: {
    type: String,
    default: '',
  },
  passValid: {
    type: Boolean,
    default: false,
  },
  validUntilLabel: {
    type: String,
    default: '',
  },
  canBuildRoute: {
    type: Boolean,
    default: false,
  },
  canAddBodyPhoto: {
    type: Boolean,
    default: false,
  },
  canDeactivate: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['build-route', 'add-body-photo', 'deactivate'])
</script>

<style scoped>
.guest-card {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #ffffff;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.guest-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08);
}

.guest-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.guest-card__actions {
  display: flex;
  gap: 0.25rem;
}

.guest-card__body {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.guest-card__avatar {
  margin-bottom: 1rem;
}

.guest-card__avatar-placeholder,
.guest-card__avatar-image {
  width: 90px;
  height: 90px;
  border-radius: 50%;
}

.guest-card__avatar-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
  color: #94a3b8;
  font-size: 2.5rem;
  box-shadow: 0 4px 10px rgba(15, 23, 42, 0.05);
}

.guest-card__avatar-image {
  object-fit: cover;
  box-shadow: 0 4px 10px rgba(15, 23, 42, 0.1);
}

.guest-card__name {
  margin: 0 0 0.25rem;
  color: #0f172a;
  font-size: 1.15rem;
  font-weight: 800;
}

.guest-card__middle-name {
  min-height: 1.2rem;
  margin: 0 0 1rem;
  color: #64748b;
  font-size: 0.9rem;
}

.guest-card__info {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.guest-card__info-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #475569;
  font-size: 0.85rem;
  font-weight: 600;
  text-align: left;
}

.guest-card__info-row i {
  color: #3b82f6;
  font-size: 1rem;
}

.guest-card__info-row--expired {
  color: #ef4444;
}

.guest-card__info-row--expired i {
  color: #ef4444;
}

.guest-card__info-row--reid {
  color: #0f766e;
}

.guest-card__info-row--reid i {
  color: #0f766e;
}
</style>
