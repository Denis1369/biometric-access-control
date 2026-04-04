<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <div class="brand-icon">
          <i class="pi pi-shield"></i>
        </div>
        <div>
          <h1>СКУД</h1>
          <p>Вход в систему управления доступом</p>
        </div>
      </div>

      <form class="login-form" @submit.prevent="submitLogin">
        <div class="form-group">
          <label>Логин</label>
          <input v-model="form.username" type="text" class="form-input" autocomplete="username" />
        </div>

        <div class="form-group">
          <label>Пароль</label>
          <input v-model="form.password" type="password" class="form-input" autocomplete="current-password" />
        </div>

        <div v-if="errorMessage" class="error-banner">
          <i class="pi pi-exclamation-triangle"></i>
          <span>{{ errorMessage }}</span>
        </div>

        <button class="btn-primary" :disabled="loading" type="submit">
          <i class="pi" :class="loading ? 'pi-spin pi-spinner' : 'pi-sign-in'"></i>
          {{ loading ? 'Вход...' : 'Войти' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../services/auth'

const auth = useAuth()
const router = useRouter()
const route = useRoute()

const loading = ref(false)
const errorMessage = ref('')
const form = reactive({
  username: '',
  password: '',
})

async function submitLogin() {
  if (!form.username.trim() || !form.password) {
    errorMessage.value = 'Введите логин и пароль'
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    const user = await auth.login(form.username.trim(), form.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : auth.getDefaultRoute(user?.role)
    router.replace(redirect || auth.getDefaultRoute(user?.role))
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || 'Не удалось выполнить вход'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 55%, #ecfeff 100%);
}

.login-card {
  width: 100%;
  max-width: 430px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 24px;
  padding: 2rem;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.08);
}

.brand {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
}

.brand-icon {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background: #dcfce7;
  color: #10b981;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.6rem;
}

.brand h1 {
  font-size: 1.5rem;
  color: #0f172a;
  margin-bottom: 0.25rem;
}

.brand p {
  color: #64748b;
  font-size: 0.92rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.form-group label {
  color: #334155;
  font-weight: 600;
  font-size: 0.9rem;
}

.form-input {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  padding: 0.85rem 1rem;
  font-size: 0.95rem;
  outline: none;
  background: #f8fafc;
}

.form-input:focus {
  border-color: #3b82f6;
  background: #ffffff;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.85rem 1rem;
  border-radius: 12px;
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecaca;
  font-size: 0.9rem;
  font-weight: 500;
}

.btn-primary {
  margin-top: 0.5rem;
  border: none;
  border-radius: 12px;
  padding: 0.9rem 1rem;
  font-weight: 700;
  font-size: 0.95rem;
  background: #2563eb;
  color: white;
  cursor: pointer;
  display: inline-flex;
  justify-content: center;
  align-items: center;
  gap: 0.6rem;
}

.btn-primary:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
</style>
