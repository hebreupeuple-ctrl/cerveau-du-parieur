import { configureStore } from '@reduxjs/toolkit'
import authReducer from './slices/authSlice.js'
import pronosticsReducer from './slices/pronosticsSlice.js'
import performanceReducer from './slices/performanceSlice.js'

export const store = configureStore({
  reducer: {
    auth: authReducer,
    pronostics: pronosticsReducer,
    performance: performanceReducer,
  },
})

export default store
