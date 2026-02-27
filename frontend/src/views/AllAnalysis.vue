<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold">Kết quả phân tích tất cả mã</h2>
      <button
        class="px-3 py-1 bg-sky text-white rounded"
        @click="triggerAnalysis"
        :disabled="loading"
      >
        Phân tích
      </button>
    </div>
    <LoadingState v-if="loading" />
    <ErrorBanner v-else-if="error" :message="error" />
    <StockTable v-else :rows="rows" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchAllAnalysis, fetchScanLatest } from '../services/api'
import LoadingState from '../components/LoadingState.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import StockTable from '../components/StockTable.vue'

const STORAGE_KEY = 'allAnalysisRows'

const rows = ref([])
const loading = ref(false)
const error = ref('')

async function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      rows.value = JSON.parse(raw)
    }
  } catch (e) {
    console.warn('failed to parse stored analysis', e)
  }
}

async function saveToStorage(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch (e) {
    console.warn('failed to save analysis', e)
  }
}

async function refreshAnalysis() {
  error.value = ''
  try {
    const res = await fetchAllAnalysis()
    rows.value = res.data || []
    saveToStorage(rows.value)
  } catch (e) {
    error.value = 'Không thể tải kết quả phân tích'
  }
}

async function triggerAnalysis() {
  loading.value = true
  error.value = ''
  try {
    // first tell backend to run a fresh scan (if already running this is a no-op)
    await fetchScanLatest()
    // then grab the updated results
    await refreshAnalysis()
  } catch (e) {
    error.value = 'Không thể chạy phân tích'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadFromStorage()
  // do not automatically refresh; user must click 'Phân tích' to update
})
</script>