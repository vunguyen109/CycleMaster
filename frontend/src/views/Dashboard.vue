<template>
  <div class="space-y-6">
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <StatCard label="Chu kỳ thị trường" :value="marketRegime?.regime || '-'" :hint="regimeHint" />
      <StatCard label="Độ tin cậy" :value="marketRegime ? marketRegime.confidence.toFixed(1) + '%' : '-'" />
      <StatCard label="Lần quét gần nhất" :value="scanLatest?.date || '-'" />
    </div>

    <section>
      <h2 class="text-lg font-semibold mb-2">Top 5 cơ hội</h2>
      <LoadingState v-if="loading" />
      <ErrorBanner v-else-if="error" :message="error" />
      <StockTable v-else :rows="topStocks" />
    </section>

    <section class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div class="p-4 bg-white rounded-xl border border-slate-200">
        <h3 class="font-semibold mb-2">Cảnh báo phân phối</h3>
        <ul class="text-sm space-y-2">
          <li v-for="a in alerts" :key="a.symbol" class="flex items-center justify-between">
            <span>{{ a.symbol }}</span>
            <RegimeBadge :regime="a.regime" />
          </li>
        </ul>
      </div>
      <div class="p-4 bg-white rounded-xl border border-slate-200">
        <h3 class="font-semibold mb-2">Danh mục theo dõi</h3>
        <ul class="text-sm space-y-2">
          <li v-for="p in portfolio" :key="p.symbol" class="flex items-center justify-between">
            <div>
              <div>{{ p.symbol }} ({{ p.quantity }})</div>
              <div v-if="p.warning" class="text-xs text-rose">{{ translateWarning(p.warning) }}</div>
            </div>
            <RegimeBadge v-if="p.latest_regime" :regime="p.latest_regime" />
          </li>
        </ul>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { fetchMarketRegime, fetchTopStocks, fetchScanLatest, fetchAlerts, fetchPortfolio } from '../services/api'
import StatCard from '../components/StatCard.vue'
import LoadingState from '../components/LoadingState.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import StockTable from '../components/StockTable.vue'
import RegimeBadge from '../components/RegimeBadge.vue'

const marketRegime = ref(null)
const topStocks = ref([])
const scanLatest = ref(null)
const alerts = ref([])
const portfolio = ref([])
const loading = ref(true)
const error = ref('')

const regimeHint = computed(() => {
  if (!marketRegime.value) return ''
  return `tính đến ${marketRegime.value.date}`
})

const translateWarning = (message) => {
  if (message === 'Holding moved to MARKDOWN') return 'Cổ phiếu đang nắm giữ chuyển sang MARKDOWN'
  return message
}

onMounted(async () => {
  try {
    const [regimeRes, topRes, scanRes, alertRes, portfolioRes] = await Promise.all([
      fetchMarketRegime(),
      fetchTopStocks(),
      fetchScanLatest(),
      fetchAlerts(),
      fetchPortfolio()
    ])
    marketRegime.value = regimeRes.data
    topStocks.value = topRes.data
    scanLatest.value = scanRes.data
    alerts.value = alertRes.data
    portfolio.value = portfolioRes.data
  } catch (e) {
    error.value = 'Không thể tải dữ liệu tổng quan'
  } finally {
    loading.value = false
  }
})
</script>
