<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setAuth } from '../api'

const router = useRouter()
const mode = ref('login') // 'login' | 'register'
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    const path = mode.value === 'login' ? '/auth/login' : '/auth/register'
    const res = await api(path, { method: 'POST', body: { username: username.value, password: password.value } })
    setAuth(res.token, res.username)
    router.push('/chat')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <form class="login-card" @submit.prevent="submit">
      <h1>LLM Chat</h1>
      <div class="tabs">
        <button type="button" :class="{ active: mode === 'login' }" @click="mode = 'login'">Вход</button>
        <button type="button" :class="{ active: mode === 'register' }" @click="mode = 'register'">Регистрация</button>
      </div>
      <label>
        Логин
        <input v-model.trim="username" autocomplete="username" required minlength="3" maxlength="64" />
      </label>
      <label>
        Пароль
        <input v-model="password" type="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" required minlength="6" />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="primary" :disabled="busy">
        {{ busy ? '…' : mode === 'login' ? 'Войти' : 'Создать аккаунт' }}
      </button>
    </form>
  </div>
</template>
