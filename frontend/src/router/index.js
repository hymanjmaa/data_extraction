import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import DocumentUpload from '../views/DocumentUpload.vue'
import TemplateManager from '../views/TemplateManager.vue'
import BatchProcess from '../views/BatchProcess.vue'
import ChatIntegration from '../views/ChatIntegration.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/documents',
    name: 'DocumentUpload',
    component: DocumentUpload
  },
  {
    path: '/templates',
    name: 'TemplateManager',
    component: TemplateManager
  },
  {
    path: '/batch',
    name: 'BatchProcess',
    component: BatchProcess
  },
  {
    path: '/chat',
    name: 'ChatIntegration',
    component: ChatIntegration
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
