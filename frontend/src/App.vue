<template>
  <div v-if="!auth.state.initialized" class="boot-screen">
    <i class="pi pi-spin pi-spinner"></i>
    <span>Загрузка системы...</span>
  </div>

  <RouterView v-else-if="route.meta.public" />

  <div v-else class="layout-wrapper">
    <aside class="sidebar">
      <div class="logo">
        <i class="pi pi-shield" style="font-size: 1.5rem; color: #10b981;"></i>
        <div>
          <h2>СКУД</h2>
          <p class="logo-subtitle">Biometric Access Control</p>
        </div>
      </div>

      <nav>
        <RouterLink
          v-for="item in visibleNavItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
        >
          <i :class="item.icon"></i>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </aside>

    <main class="main-content">
      <header class="topbar">
        <span>Система контроля и управления доступом</span>
        <div class="user-profile">
          <div class="user-meta">
            <strong>{{ auth.username.value }}</strong>
            <small>{{ currentRoleLabel }}</small>
          </div>
          <button class="logout-btn" @click="handleLogout">
            <i class="pi pi-sign-out"></i>
            Выйти
          </button>
        </div>
      </header>

      <div class="content">
        <RouterView />
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from './services/auth'

const auth = useAuth()
const route = useRoute()
const router = useRouter()

const roleLabels = {
  super_admin: 'Super Admin',
  checkpoint_operator: 'Оператор КПП',
}

const navItems = [
  { to: '/', label: 'Дашборд', icon: 'pi pi-home', roles: ['super_admin'] },
  { to: '/employees', label: 'Сотрудники', icon: 'pi pi-users', roles: ['super_admin'] },
  { to: '/cameras', label: 'Камеры', icon: 'pi pi-video', roles: ['super_admin', 'checkpoint_operator'] },
  { to: '/route', label: 'Проходная', icon: 'pi pi-sign-in', roles: ['super_admin', 'checkpoint_operator'] },
  { to: '/tracking', label: 'План здания', icon: 'pi pi-building', roles: ['super_admin', 'checkpoint_operator'] },
  { to: '/video-analysis', label: 'Анализ видео', icon: 'pi pi-play-circle', roles: ['super_admin', 'checkpoint_operator'] },
  { to: '/guests', label: 'Гости', icon: 'pi pi-user-plus', roles: ['super_admin', 'checkpoint_operator'] },
  { to: '/departments', label: 'Отделы', icon: 'pi pi-sitemap', roles: ['super_admin'] },
  { to: '/users', label: 'Пользователи', icon: 'pi pi-lock', roles: ['super_admin'] },
]

const visibleNavItems = computed(() => navItems.filter((item) => auth.hasAnyRole(...item.roles)))
const currentRoleLabel = computed(() => roleLabels[auth.role.value] || 'Пользователь')

function handleLogout() {
  auth.logout({ redirect: false })
  router.replace('/login')
}
</script>

<style>
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  font-family: var(--font-family, sans-serif);
}

body {
  background-color: #f8fafc;
  color: #334155;
}

.boot-screen {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  color: #0f172a;
  font-weight: 600;
}

.layout-wrapper {
  display: flex;
  height: 100vh;
}

.sidebar {
  width: 260px;
  background-color: #ffffff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
}

.logo {
  min-height: 75px;
  padding: 1.25rem 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  border-bottom: 1px solid #e2e8f0;
}

.logo h2 {
  font-size: 1.2rem;
  color: #0f172a;
}

.logo-subtitle {
  margin-top: 0.15rem;
  font-size: 0.75rem;
  color: #64748b;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  color: #64748b;
  text-decoration: none;
  transition: background 0.2s, color 0.2s;
}

.nav-link:hover,
.router-link-active {
  background-color: #f1f5f9;
  color: #10b981;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  min-height: 75px;
  background-color: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2rem;
  font-weight: 500;
  gap: 1rem;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.user-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  line-height: 1.2;
}

.user-meta strong {
  color: #0f172a;
  font-size: 0.95rem;
}

.user-meta small {
  color: #64748b;
  font-size: 0.78rem;
}

.logout-btn {
  border: none;
  background: #f1f5f9;
  color: #334155;
  border-radius: 10px;
  padding: 0.65rem 1rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
}

.logout-btn:hover {
  background: #e2e8f0;
}

.content {
  padding: 2rem;
  flex: 1;
  overflow-y: auto;
}
</style>
