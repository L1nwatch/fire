import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', name: 'dashboard', component: () => import('./pages/DashboardPage.vue') },
    { path: '/monthly', name: 'monthly', component: () => import('./pages/MonthlyReportPage.vue') },
    { path: '/ledger', name: 'ledger', component: () => import('./pages/LedgerPage.vue') },
    { path: '/assets', name: 'assets', component: () => import('./pages/HoldingsPage.vue') },
    { path: '/investment', name: 'investment', component: () => import('./pages/HoldingsPage.vue') },
    { path: '/holdings', redirect: '/assets' },
    { path: '/forecast', redirect: '/investment' },
  ],
})

export default router
