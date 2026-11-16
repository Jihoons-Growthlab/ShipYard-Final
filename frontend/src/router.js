import { createRouter, createWebHistory } from 'vue-router'
import { getToken, onUnauthorized } from './api/client'
import { endSession } from './stores/session'
import LoginView from './views/LoginView.vue'
import ShellView from './views/ShellView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView },
    { path: '/', component: ShellView },
    { path: '/:rest(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const t = getToken()
  if (!t && to.path !== '/login') return '/login'
  if (t && to.path === '/login') return '/'
  return true
})

onUnauthorized(() => {
  endSession()
  router.push('/login')
})
