<template>
  <div class="layout-wrapper">
    <aside class="sidebar">
      <div class="logo">
        <i class="pi pi-shield" style="font-size: 1.5rem; color: #10b981;"></i>
        <h2>СКУД</h2>
      </div>
      <nav>
        <RouterLink to="/" class="nav-link"><i class="pi pi-home"></i> Дашборд</RouterLink>
        <RouterLink to="/employees" class="nav-link"><i class="pi pi-users"></i> Сотрудники</RouterLink>
        <RouterLink to="/cameras" class="nav-link"><i class="pi pi-video"></i> Камеры</RouterLink>
        <RouterLink to="/route" class="nav-link"><i class="pi pi-map"></i> Маршруты</RouterLink>
      </nav>
    </aside>

    <main class="main-content">
      <header class="topbar">
        <span>Система контроля и управления доступом</span>
        <div class="user-profile">
          <i class="pi pi-user"></i> Администратор
        </div>
      </header>
      
      <div class="content">
        <RouterView />
      </div>
    </main>
  </div>
</template>

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

.layout-wrapper {
  display: flex;
  height: 100vh;
}

.sidebar {
  width: 250px;
  background-color: #ffffff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
}

.logo {
  height: 75px;
  padding: 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  border-bottom: 1px solid #e2e8f0;
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

.nav-link:hover, .router-link-active {
  background-color: #f1f5f9;
  color: #10b981;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.topbar {
  height: 75px;
  background-color: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2rem;
  font-weight: 500;
}

.content {
  padding: 2rem;
  flex: 1;
  overflow-y: auto;
}
</style>