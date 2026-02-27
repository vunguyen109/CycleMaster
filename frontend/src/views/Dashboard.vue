<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Chu kỳ thị trường" :value="regimeDisplay" :hint="regimeHint" />
        <StatCard label="Độ tin cậy" :value="marketRegime ? marketRegime.confidence.toFixed(1) + '%' : '-'" />
        <StatCard label="Lần quét gần nhất" :value="scanLatest?.date || '-'" />
      </div>
      <button
        class="px-3 py-1 bg-sky text-white rounded"
        @click="triggerAnalysis"
        :disabled="loading"
      >
        Phân tích
      </button>
    </div>

    <section>
      <h2 class="text-lg font-semibold mb-2">Top Trade Setups</h2>
      <LoadingState v-if="loading" />
      <ErrorBanner v-else-if="error" :message="error" />
      <StockTable v-else :rows="topTrades" />
      </section>

    <section class="grid grid-cols-1 md:grid-cols-1 gap-4">
      <div class="p-4 bg-white rounded-xl border border-slate-200">
        <h3 class="font-semibold mb-2">Danh mục nắm giữ</h3>
        <div class="flex flex-wrap items-end gap-2 mb-3 text-sm">
          <div>
            <div class="text-xs text-slate-500">Mã</div>
            <input v-model="form.symbol" class="border border-slate-300 rounded px-2 py-1 w-24" placeholder="HPG" />
          </div>
          <div>
            <div class="text-xs text-slate-500">Giá mua</div>
            <input v-model="form.avg_price" type="number" class="border border-slate-300 rounded px-2 py-1 w-28" placeholder="25.5" />
          </div>
          <div>
            <div class="text-xs text-slate-500">Số lượng</div>
            <input v-model="form.quantity" type="number" class="border border-slate-300 rounded px-2 py-1 w-28" placeholder="100" />
          </div>
          <button @click="submitPortfolio" :disabled="portfolioSaving" class="px-3 py-1 bg-sky text-white rounded">
            {{ editingSymbol ? 'Cập nhật' : 'Thêm' }}
          </button>
          <button v-if="editingSymbol" @click="resetForm" class="px-3 py-1 border border-slate-300 rounded">
            Hủy
          </button>
        </div>
        <div class="overflow-auto">
          <table class="min-w-full text-sm">
            <thead class="text-slate-500">
              <tr>
                <th class="text-left py-2">Mã</th>
                <th class="text-left py-2">Giá mua (nghìn đ)</th>
                <th class="text-left py-2">Giá hiện tại (nghìn đ)</th>
                <th class="text-left py-2">Ngày cập nhật</th>
                <th class="text-left py-2">Số lượng</th>
                <th class="text-left py-2">Lời/lỗ (nghìn đ)</th>
                <th class="text-left py-2">Chu kỳ</th>
                <th class="text-left py-2">Entry (nghìn đ)</th>
                <th class="text-left py-2">Target (nghìn đ)</th>
                <th class="text-left py-2">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in portfolio" :key="p.symbol" class="border-t border-slate-100">
                <td class="py-2">{{ p.symbol }}</td>
                <td class="py-2">{{ formatMoney(p.avg_price) }}</td>
                <td class="py-2">{{ formatMoney(p.last_close) }}</td>
                <td class="py-2 text-xs">{{ p.last_close_date || '-' }}</td>
                <td class="py-2">{{ formatNumber(p.quantity) }}</td>
                <td class="py-2" :class="p.pnl_vnd >= 0 ? 'text-mint' : 'text-rose'">
                  {{ formatPnL(p.pnl_vnd || 0) }}
                </td>
                <td class="py-2">
                  <RegimeBadge v-if="p.latest_regime" :regime="p.latest_regime" />
                </td>
                <td class="py-2">{{ formatMoney(p.entry) }}</td>
                <td class="py-2">{{ formatMoney(p.target) }}</td>
                <td class="py-2 flex gap-2">
                  <button @click="editPortfolio(p)" class="text-sky">Sửa</button>
                  <button @click="removePortfolio(p.symbol)" class="text-rose">Xóa</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="portfolioWarning" class="mt-2 text-xs text-rose">{{ portfolioWarning }}</div>
      </div>
    </section>

    <section>
      <CycleMoneyFlowChart :rows="topTrades" :series="vnindexSeries" />
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
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, reactive } from 'vue'
import { fetchMarketRegime, fetchAllAnalysis, fetchScanLatest, fetchAlerts, fetchPortfolio, fetchVnindexSeries, createPortfolioItem, updatePortfolioItem, deletePortfolioItem } from '../services/api'
import StatCard from '../components/StatCard.vue'
import LoadingState from '../components/LoadingState.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import StockTable from '../components/StockTable.vue'
import RegimeBadge from '../components/RegimeBadge.vue'
import CycleMoneyFlowChart from '../components/CycleMoneyFlowChart.vue'

const marketRegime = ref(null)
const allAnalysis = ref([])   // entire universe from /analysis/latest
const topTrades = computed(() => {
  // sort by score desc and take top 10; optionally filter very low liquidity
  let arr = Array.isArray(allAnalysis.value) ? [...allAnalysis.value] : []
  // ensure action field exists
  arr = arr.map(r => {
    if (!r.action) {
      const score = r.score ?? 0
      return {
        ...r,
        action: score >= 75 ? 'BUY' : score >= 60 ? 'WATCH' : 'AVOID'
      }
    }
    return r
  })
  // sort by highest setup_quality first (fallback to score if missing)
  arr.sort((a, b) => {
    const qa = a.setup_quality ?? a.score ?? 0
    const qb = b.setup_quality ?? b.score ?? 0
    return qb - qa
  })
  const slice = arr.slice(0, 10)
  // pad if under 10
  while (slice.length < 10) {
    slice.push({ symbol: '-', score: 0, phase: '-', action: '-', entry: null, stop: null, target: null, rr: null, setup_quality: 0 })
  }
  return slice
})
const scanLatest = ref(null)
const alerts = ref([])
const portfolio = ref([])
const vnindexSeries = ref([])
const loading = ref(true)
const error = ref('')
const portfolioSaving = ref(false)
const editingSymbol = ref('')
const form = reactive({
  symbol: '',
  avg_price: '',
  quantity: ''
})

const regimeHint = computed(() => {
  if (!marketRegime.value) return ''
  const parts = [`tính đến ${marketRegime.value.date}`]
  if (marketRegime.value.prev_regime) {
    const diff = marketRegime.value.confidence_change
    const diffText = diff === null || diff === undefined ? '' : `, ${diff.toFixed(1)}%`
    const map = {
      ACCUMULATION: 'Tích lũy',
      ACCUMULATION_STRONG: 'Tích lũy mạnh',
      ACCUMULATION_WEAK: 'Tích lũy yếu',
      MARKUP: 'Đẩy giá',
      DISTRIBUTION: 'Phân phối',
      MARKDOWN: 'Đè giá',
      NEUTRAL: 'Trung lập'
    }
    const prev = map[marketRegime.value.prev_regime] || marketRegime.value.prev_regime
    parts.push(`trước đó: ${prev}${diffText}`)
  }
  return parts.join(' | ')
})

const regimeDisplay = computed(() => {
  if (!marketRegime.value) return '-'
  if (marketRegime.value.confidence < 55) return 'Trung lập'
  const map = {
    ACCUMULATION: 'Tích lũy',
    ACCUMULATION_STRONG: 'Tích lũy mạnh',
    ACCUMULATION_WEAK: 'Tích lũy yếu',
    MARKUP: 'Đẩy giá',
    DISTRIBUTION: 'Phân phối',
    MARKDOWN: 'Đè giá',
    NEUTRAL: 'Trung lập'
  }
  return map[marketRegime.value.regime] || marketRegime.value.regime
})

const translateWarning = (message) => {
  if (message === 'Holding moved to MARKDOWN') return 'Cổ phiếu đang nắm giữ chuyển sang MARKDOWN'
  return message
}

const portfolioWarning = computed(() => {
  const warnings = portfolio.value.map(p => p.warning).filter(Boolean)
  if (!warnings.length) return ''
  return warnings.map(translateWarning).join('  ')
})

const formatNumber = (value) => {
  if (value === null || value === undefined) return '-'
  return Number(value).toLocaleString('vi-VN')
}

const formatMoney = (value) => {
  if (value === null || value === undefined || value === '-' || value === '') return '-'
  const num = Number(value)
  if (Number.isNaN(num)) return value
  return (num / 1000).toLocaleString('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

const formatPnL = (value) => {
  if (value === null || value === undefined || value === '-' || value === '') return '-'
  const num = Number(value)
  if (Number.isNaN(num)) return value
  // show profit/loss in thousands
  return (num / 1000).toLocaleString('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

const formatZone = (low, high) => {
  if (low === null || low === undefined || high === null || high === undefined) return '-'
  const a = Number(low)
  const b = Number(high)
  if (Number.isNaN(a) || Number.isNaN(b)) return '-'
  const left = (a / 1000).toLocaleString('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
  const right = (b / 1000).toLocaleString('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
  return `${left} - ${right}`
}

const resetForm = () => {
  form.symbol = ''
  form.avg_price = ''
  form.quantity = ''
  editingSymbol.value = ''
}

const STORAGE_KEY = 'dashboardData'

const refreshPortfolio = async () => {
  const res = await fetchPortfolio()
  portfolio.value = res.data
}

const submitPortfolio = async () => {
  if (!form.symbol || !form.avg_price || !form.quantity) return
  portfolioSaving.value = true
  try {
    const payload = {
      symbol: form.symbol.trim().toUpperCase(),
      avg_price: Number(form.avg_price),
      quantity: Number(form.quantity)
    }
    if (editingSymbol.value) {
      await updatePortfolioItem(editingSymbol.value, payload)
    } else {
      await createPortfolioItem(payload)
    }
    await refreshPortfolio()
    resetForm()
  } catch (e) {
    error.value = 'Không thể cập nhật danh mục nắm giữ'
  } finally {
    portfolioSaving.value = false
  }
}

const editPortfolio = (item) => {
  editingSymbol.value = item.symbol
  form.symbol = item.symbol
  form.avg_price = item.avg_price
  form.quantity = item.quantity
}

const removePortfolio = async (symbol) => {
  portfolioSaving.value = true
  try {
    await deletePortfolioItem(symbol)
    await refreshPortfolio()
  } catch (e) {
    error.value = 'Không thể xóa khỏi danh mục nắm giữ'
  } finally {
    portfolioSaving.value = false
  }
}

async function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const obj = JSON.parse(raw)
      scanLatest.value = obj.scanLatest
      marketRegime.value = obj.marketRegime
      allAnalysis.value = obj.allAnalysis
      alerts.value = obj.alerts
      vnindexSeries.value = obj.vnindexSeries
    }
  } catch (e) {
    console.warn('failed to parse dashboard data', e)
  }
}

async function saveToStorage() {
  try {
    const obj = {
      scanLatest: scanLatest.value,
      marketRegime: marketRegime.value,
      allAnalysis: allAnalysis.value,
      alerts: alerts.value,
      vnindexSeries: vnindexSeries.value
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(obj))
  } catch (e) {
    console.warn('failed to save dashboard data', e)
  }
}

async function refreshAll() {
  error.value = ''
  try {
    const scanRes = await fetchScanLatest()
    scanLatest.value = scanRes.data
    const [regimeRes, allRes, alertRes, vnindexRes] = await Promise.all([
      fetchMarketRegime(),
      fetchAllAnalysis(),
      fetchAlerts(),
      fetchVnindexSeries()
    ])
    marketRegime.value = regimeRes.data
    allAnalysis.value = allRes.data
    alerts.value = alertRes.data
    vnindexSeries.value = vnindexRes.data.series

    await refreshPortfolio()
    saveToStorage()
  } catch (e) {
    error.value = 'Không thể tải dữ liệu tổng quan'
  }
}

async function triggerAnalysis() {
  loading.value = true
  try {
    await refreshAll()
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadFromStorage()
  // always fetch portfolio since user may change it independently
  await refreshPortfolio()
  // user must click Phân tích to update the rest
  loading.value = false
})
</script>
