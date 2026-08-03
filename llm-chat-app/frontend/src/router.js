import { createRouter, createWebHashHistory } from 'vue-router'
import { getToken } from './api'
import LoginView from './views/LoginView.vue'
import ChatView from './views/ChatView.vue'

// Hash-роутер: на изолированной машине статику отдаёт FastAPI,
// deep-link'и работают без серверных fallback'ов.
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    { path: '/login', component: LoginView },
    { path: '/chat', component: ChatView },
  ],
})

router.beforeEach((to) => {
  if (to.path !== '/login' && !getToken()) return '/login'
  if (to.path === '/login' && getToken()) return '/chat'
})

export default router
