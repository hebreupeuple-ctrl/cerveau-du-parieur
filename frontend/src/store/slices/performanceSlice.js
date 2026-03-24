import { createSlice } from '@reduxjs/toolkit'

const performanceSlice = createSlice({
  name: 'performance',
  initialState: {
    data: null,
    loading: false,
    error: null,
  },
  reducers: {},
})

export default performanceSlice.reducer
