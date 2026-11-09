import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/authStore'
import './assets/styles/variables.css'
import './assets/styles/base.css'
import './assets/styles/utilities.css'
import './assets/styles/ui.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
useAuthStore(pinia).restoreSession()
app.use(router)

app.mount('#app')
