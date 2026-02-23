<template>
  <div class="space-y-6">
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <StatCard label="Chu kỳ thị trường" :value="regimeDisplay" :hint="regimeHint" />
      <StatCard label="Độ tin cậy" :value="marketRegime ? marketRegime.confidence.toFixed(1) + '%' : '-'" />
      <StatCard label="Lần quét gần nhất" :value="scanLatest?.date || '-'" />
    </div>

    <section>
      <h2 class="text-lg font-semibold mb-2">Top tiềm năng</h2>
      <LoadingState v-if="loading" />
      <ErrorBanner v-else-if="error" :message="error" />
      <StockTable v-else :rows="topStocks" />
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
                <th class="text-left py-2">Số lượng</th>
                <th class="text-left py-2">Lời/lỗ (nghìn đ)</th>
                <th class="text-left py-2">Chu kỳ</th>
                <th class="text-left py-2">Vùng mua (nghìn đ)</th>
                <th class="text-left py-2">Chốt lời (nghìn đ)</th>
                <th class="text-left py-2">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in portfolio" :key="p.symbol" class="border-t border-slate-100">
                <td class="py-2">{{ p.symbol }}</td>
                <td class="py-2">{{ formatMoney(p.avg_price) }}</td>
                <td class="py-2">{{ formatNumber(p.quantity) }}</td>
                <td class="py-2" :class="p.pnl_vnd >= 0 ? 'text-mint' : 'text-rose'">
                  {{ formatMoney(p.pnl_vnd || 0) }}
                </td>
                <td class="py-2">
                  <RegimeBadge v-if="p.latest_regime" :regime="p.latest_regime" />
                </td>
                <td class="py-2">{{ formatZone(p.buy_zone) }}</td>
                <td class="py-2">{{ formatMoney(p.take_profit) }}</td>
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
      <CycleMoneyFlowChart :rows="topStocks" :series="vnindexSeries" />
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
import { fetchMarketRegime, fetchTopStocks, fetchScanLatest, fetchAlerts, fetchPortfolio, fetchVnindexSeries, createPortfolioItem, updatePortfolioItem, deletePortfolioItem } from '../services/api'
import StatCard from '../components/StatCard.vue'
import LoadingState from '../components/LoadingState.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import StockTable from '../components/StockTable.vue'
import RegimeBadge from '../components/RegimeBadge.vue'
import CycleMoneyFlowChart from '../components/CycleMoneyFlowChart.vue'

const marketRegime = ref(null)
const topStocks = ref([])
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

const resetForm = () => {
  form.symbol = ''
  form.avg_price = ''
  form.quantity = ''
  editingSymbol.value = ''
}

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

onMounted(async () => {
  try {
    const scanRes = await fetchScanLatest()
    scanLatest.value = scanRes.data
    const [regimeRes, topRes, alertRes, portfolioRes, vnindexRes] = await Promise.all([
      fetchMarketRegime(),
      fetchTopStocks(),
      fetchAlerts(),
      fetchPortfolio(),
      fetchVnindexSeries()
    ])
    marketRegime.value = regimeRes.data
    topStocks.value = topRes.data
    alerts.value = alertRes.data
    portfolio.value = portfolioRes.data
    vnindexSeries.value = vnindexRes.data.series
  } catch (e) {
    error.value = 'Không thể tải dữ liệu tổng quan'
  } finally {
    loading.value = false
  }
})
</script>
