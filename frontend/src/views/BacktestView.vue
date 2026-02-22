<template>
  <div class="space-y-4">
    <div class="flex items-center gap-2">
      <input v-model="symbol" class="border border-slate-300 rounded px-2 py-1" placeholder="Mã cổ phiếu" />
      <select v-model="strategy" class="border border-slate-300 rounded px-2 py-1">
        <option value="breakout20">Breakout 20 ngày</option>
        <option value="accumulation">Tích lũy + Bùng nổ</option>
      </select>
      <button @click="run" class="px-3 py-1 bg-sky text-white rounded">Chạy</button>
    </div>

    <LoadingState v-if="loading" />
    <ErrorBanner v-else-if="error" :message="error" />

    <div v-else-if="result" class="grid gap-4">
      <div class="p-4 bg-white rounded-xl border border-slate-200">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>Tỷ lệ thắng: {{ (result.win_rate * 100).toFixed(1) }}%</div>
          <div>Drawdown tối đa: {{ (result.max_drawdown * 100).toFixed(1) }}%</div>
          <div>R:R trung bình: {{ result.avg_rr.toFixed(2) }}</div>
        </div>
      </div>
      <div class="p-4 bg-white rounded-xl border border-slate-200">
        <div ref="chart" class="w-full h-64"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import * as echarts from 'echarts'
import { fetchBacktest } from '../services/api'
import LoadingState from '../components/LoadingState.vue'
import ErrorBanner from '../components/ErrorBanner.vue'

const symbol = ref('HPG')
const strategy = ref('breakout20')
const result = ref(null)
const loading = ref(false)
const error = ref('')
const chart = ref(null)
let instance = null

const renderChart = () => {
  if (!result.value) return
  if (!instance) instance = echarts.init(chart.value)
  const data = result.value.equity_curve.map(p => p.equity)
  instance.setOption({
    xAxis: { type: 'category', data: data.map((_, i) => i) },
    yAxis: { type: 'value' },
    series: [{ type: 'line', data }]
  })
}

const run = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchBacktest(symbol.value, strategy.value)
    result.value = res.data
    await nextTick()
    renderChart()
  } catch (e) {
    error.value = 'Không thể chạy backtest'
  } finally {
    loading.value = false
  }
}
</script>
