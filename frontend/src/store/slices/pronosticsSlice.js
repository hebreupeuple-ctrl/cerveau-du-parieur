import { createSlice } from '@reduxjs/toolkit'

const pronosticsSlice = createSlice({
  name: 'pronostics',
  initialState: {
    today: null,
    loading: false,
    error: null,
  },
  reducers: {},
})

export default pronosticsSlice.reducer
