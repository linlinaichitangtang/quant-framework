import { defineStore } from 'pinia'
import { getOverview } from '@/api'

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    overview: null,
    loading: false
  }),

  actions: {
    async fetchOverview() {
      this.loading = true
      try {
        const data = await getOverview()
        this.overview = data
        return data
      } catch (error) {
        console.error('Failed to fetch overview:', error)
        throw error
      } finally {
        this.loading = false
      }
    }
  }
})
