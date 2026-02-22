import { createRouter, createWebHistory } from 'vue-router'

/**
 * Router
 * Educational Note: Vue Router uses dynamic imports (lazy loading) for route
 * components. This is equivalent to React.lazy() — the component bundle is
 * only fetched when the user navigates to that route.
 *
 * Route structure mirrors the React BrowserRouter setup:
 *   /projects/:projectId → ProjectWorkspaceRoute (loads project + renders workspace)
 *   /*                   → DashboardRoute (catch-all with auth guard)
 */
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/projects/:projectId',
      component: () => import('@/components/project/ProjectWorkspaceRoute.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      component: () => import('@/components/dashboard/DashboardRoute.vue'),
    },
  ],
})

export default router
