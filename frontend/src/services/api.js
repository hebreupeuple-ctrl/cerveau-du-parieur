import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.reload()
    }
    const data = error.response?.data || {}
    // Normalise le message d'erreur en un champ unique peu importe le format backend
    if (!data.error) {
      const msg = data.detail?.message || data.detail || data.message || 'Erreur inconnue'
      data.error = { message: typeof msg === 'string' ? msg : JSON.stringify(msg) }
    }
    return Promise.reject(data)
  }
)

export default api
