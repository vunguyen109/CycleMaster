<template>
  <div class="space-y-4">
    <h2 class="text-lg font-semibold">Danh mục theo dõi</h2>

    <div class="p-4 bg-white rounded-xl border border-slate-200">
      <div class="text-sm font-semibold mb-2">Thêm mã theo dõi</div>
      <div class="flex items-end gap-2 text-sm">
        <div>
          <div class="text-xs text-slate-500">Mã</div>
          <input v-model="symbol" class="border border-slate-300 rounded px-2 py-1 w-28" placeholder="HPG" />
        </div>
        <button @click="addSymbol" class="px-3 py-1 bg-sky text-white rounded" :disabled="saving">
          Thêm
        </button>
      </div>
    </div>

    <div class="p-4 bg-white rounded-xl border border-slate-200">
      <div class="text-sm font-semibold mb-2">Danh sách mã theo dõi</div>
      <LoadingState v-if="loading" />
      <ErrorBanner v-else-if="error" :message="error" />
      <ul v-else class="text-sm space-y-2">
        <li v-for="w in watchlist" :key="w.symbol" class="flex items-center justify-between">
          <span>{{ w.symbol }}</span>
          <button @click="removeSymbol(w.symbol)" class="text-rose">Xóa</button>
        </li>
      </ul>
    </div>

    <div>
      <h3 class="text-sm font-semibold mb-2">Xếp hạng theo dõi</h3>
      <LoadingState v-if="loadingTop" />
      <ErrorBanner v-else-if="errorTop" :message="errorTop" />
      <StockTable v-else :rows="rows" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchTopStocks, fetchWatchlist, addWatchlist, deleteWatchlist } from '../services/api'
import LoadingState from '../components/LoadingState.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import StockTable from '../components/StockTable.vue'

const watchlist = ref([])
const rows = ref([])
const loading = ref(true)
const loadingTop = ref(true)
const error = ref('')
const errorTop = ref('')
const saving = ref(false)
const symbol = ref('')

const loadWatchlist = async () => {
  const res = await fetchWatchlist()
  watchlist.value = res.data
}

const loadTop = async () => {
  const res = await fetchTopStocks()
  rows.value = res.data
}

const addSymbol = async () => {
  if (!symbol.value) return
  saving.value = true
  try {
    await addWatchlist({ symbol: symbol.value })
    symbol.value = ''
    await loadWatchlist()
    await loadTop()
  } catch (e) {
    error.value = 'Không thể thêm mã theo dõi'
  } finally {
    saving.value = false
  }
}

const removeSymbol = async (sym) => {
  saving.value = true
  try {
    await deleteWatchlist(sym)
    await loadWatchlist()
    await loadTop()
  } catch (e) {
    error.value = 'Không thể xóa mã theo dõi'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    await loadWatchlist()
  } catch (e) {
    error.value = 'Không thể tải danh mục theo dõi'
  } finally {
    loading.value = false
  }

  try {
    await loadTop()
  } catch (e) {
    errorTop.value = 'Không thể tải xếp hạng theo dõi'
  } finally {
    loadingTop.value = false
  }
})
</script>
