import { defineStore } from 'pinia'
import { getBacktestResults, getBacktestDetail, runBacktest, deleteBacktest } from '@/api'

export const useBacktestStore = defineStore('backtest', {
  state: () => ({
    results: [],
    total: 0,
    currentDetail: null,
    loading: false,
    running: false,
  }),

  actions: {
    async fetchResults(params = {}) {
      this.loading = true
      try {
        const data = await getBacktestResults(params)
        this.results = data.data || []
        this.total = data.total || 0
        return data
      } catch (error) {
        console.error('获取回测列表失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },

    async fetchDetail(backtestId) {
      this.loading = true
      try {
        const data = await getBacktestDetail(backtestId)
        this.currentDetail = data
        return data
      } catch (error) {
        console.error('获取回测详情失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },

    async runNewBacktest(config) {
      this.running = true
      try {
        const data = await runBacktest(config)
        return data
      } catch (error) {
        console.error('运行回测失败:', error)
        throw error
      } finally {
        this.running = false
      }
    },

    async removeBacktest(backtestId) {
      try {
        await deleteBacktest(backtestId)
        // 从列表中移除
        this.results = this.results.filter(r => r.id !== backtestId)
        if (this.currentDetail?.id === backtestId) {
          this.currentDetail = null
        }
      } catch (error) {
        console.error('删除回测失败:', error)
        throw error
      }
    },
  },
})
