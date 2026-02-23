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
        <div class="flex flex-wrap gap-2 mt-3">
          <LiquidityBadge :score="detail.features.liquidity_score" />
          <SetupStatusBadge :status="detail.suggested_trade.setup_status" />
          <MarketAlignmentBadge :alignment="detail.suggested_trade.market_alignment" />
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 text-sm">
          <div>RSI: {{ detail.features.rsi.toFixed(1) }}</div>
          <div>MACD: {{ detail.features.macd.toFixed(2) }}</div>
          <div>ADX: {{ detail.features.adx.toFixed(1) }}</div>
          <div>Tỷ lệ khối lượng: {{ detail.features.volume_ratio.toFixed(2) }}</div>
          <div>ATR: {{ formatMoney(detail.features.atr) }}</div>
          <div>MA20: {{ formatMoney(detail.features.ma20) }}</div>
          <div>MA50: {{ formatMoney(detail.features.ma50) }}</div>
          <div>MA100: {{ formatMoney(detail.features.ma100) }}</div>
        </div>
      </div>
      <div class="p-4 bg-white rounded-xl border border-slate-200">
        <h3 class="font-semibold mb-2">Gợi ý giao dịch (nghìn đ)</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>Vùng mua: {{ formatZone(detail.suggested_trade.buy_zone) }}</div>
          <div>Chốt lời: {{ formatMoney(detail.suggested_trade.take_profit) }}</div>
          <div>Cắt lỗ: {{ formatMoney(detail.suggested_trade.stop_loss) }}</div>
          <div>R:R: {{ formatRisk(detail.suggested_trade.risk_reward) }}</div>
          <div>Tier: {{ detail.suggested_trade.setup_tier || '-' }}</div>
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
import LiquidityBadge from '../components/LiquidityBadge.vue'
import SetupStatusBadge from '../components/SetupStatusBadge.vue'
import MarketAlignmentBadge from '../components/MarketAlignmentBadge.vue'

const route = useRoute()
const symbol = route.params.symbol
const detail = ref(null)
const loading = ref(true)
const error = ref('')

const formatMoney = (value) => {
  if (value === null || value === undefined || value === '-' || value === '') return '-'
  const num = Number(value)
  if (Number.isNaN(num)) return value
  return (num / 1000).toLocaleString('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

const formatZone = (zone) => {
  if (!zone || zone === '-') return '-'
  const parts = String(zone).split('-')
  if (parts.length !== 2) return formatMoney(zone)
  const a = Number(parts[0])
  const b = Number(parts[1])
  if (Number.isNaN(a) || Number.isNaN(b)) return zone
  const left = (a / 1000).toLocaleString('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
  const right = (b / 1000).toLocaleString('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
  return `${left} - ${right}`
}

const formatRisk = (value) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return Number(value).toFixed(2)
}

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
