<template>
  <div>
    <h2 class="text-lg font-semibold mb-4">Chi tiết cổ phiếu: {{ symbol }}</h2>
    <LoadingState v-if="loading" />
    <ErrorBanner v-else-if="error" :message="error" />
    <div v-else class="grid gap-4">
      <div class="p-4 bg-white rounded-xl border border-slate-200">
        <div class="flex items-center justify-between">
          <div class="text-xl font-semibold">{{ detail.symbol }}</div>
          <RegimeBadge :regime="detail.regime" />
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 text-sm">
          <div>RSI: {{ detail.features.rsi.toFixed(1) }}</div>
          <div>MACD: {{ detail.features.macd.toFixed(2) }}</div>
          <div>ADX: {{ detail.features.adx.toFixed(1) }}</div>
          <div>Tỷ lệ khối lượng: {{ detail.features.volume_ratio.toFixed(2) }}</div>
          <div>ATR: {{ detail.features.atr.toFixed(2) }}</div>
          <div>MA20: {{ detail.features.ma20.toFixed(2) }}</div>
          <div>MA50: {{ detail.features.ma50.toFixed(2) }}</div>
          <div>MA100: {{ detail.features.ma100.toFixed(2) }}</div>
        </div>
      </div>
      <div class="p-4 bg-white rounded-xl border border-slate-200">
        <h3 class="font-semibold mb-2">Gợi ý giao dịch</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>Vùng mua: {{ detail.suggested_trade.buy_zone }}</div>
          <div>Chốt lời: {{ detail.suggested_trade.take_profit }}</div>
          <div>Cắt lỗ: {{ detail.suggested_trade.stop_loss }}</div>
          <div>R:R: {{ detail.suggested_trade.risk_reward.toFixed(2) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { fetchStockDetail } from '../services/api'
import LoadingState from '../components/LoadingState.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import RegimeBadge from '../components/RegimeBadge.vue'

const route = useRoute()
const symbol = route.params.symbol
const detail = ref(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const res = await fetchStockDetail(symbol)
    detail.value = res.data
  } catch (e) {
    error.value = 'Không thể tải chi tiết cổ phiếu'
  } finally {
    loading.value = false
  }
})
</script>
