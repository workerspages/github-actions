import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Dashboard from '../views/Dashboard.vue'
import Secrets from '../views/Secrets.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', component: Login },
    { 
      path: '/', 
      name: 'dashboard', 
      component: Dashboard,
      meta: { requiresAuth: true }
    },
    { 
      path: '/secrets', 
      name: 'secrets', 
      component: Secrets,
      meta: { requiresAuth: true }
    }
  ]
})

// 路由守卫：检查是否有 Token
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
