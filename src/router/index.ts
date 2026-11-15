import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    subtitle?: string
  }
}

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: { name: 'inbox' } },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('../pages/chat/ChatPage.vue'),
    meta: { title: 'Support · Tongyi Demo Store' },
  },
  {
    path: '/console',
    component: () => import('../layouts/ConsoleLayout.vue'),
    redirect: { name: 'inbox' },
    children: [
      {
        path: 'inbox',
        name: 'inbox',
        component: () => import('../pages/console/InboxPage.vue'),
        meta: { title: '收件箱', subtitle: '需要人工跟进的客户会话' },
      },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('../pages/console/DashboardPage.vue'),
        meta: { title: '数据看板', subtitle: '咨询量、意图与客户语言' },
      },
      {
        path: 'catalog',
        name: 'catalog',
        component: () => import('../pages/console/CatalogPage.vue'),
        meta: { title: '商品资料', subtitle: 'Agent 检索、报价时使用的商品数据' },
      },
      {
        path: 'system',
        name: 'system',
        component: () => import('../pages/console/SystemPage.vue'),
        meta: { title: '系统状态', subtitle: '后端、模型与数据库的连接情况' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('../pages/NotFoundPage.vue'),
    meta: { title: '页面不存在' },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  const title = to.meta.title ?? '通译智联'
  document.title = to.path.startsWith('/console') ? `${title} · 通译智联商家控制台` : title
})

export default router
