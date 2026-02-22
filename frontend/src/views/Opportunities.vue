<template>
  <div>
    <h2 class="text-lg font-semibold mb-4">Cơ hội nổi bật</h2>
    <LoadingState v-if="loading" />
    <ErrorBanner v-else-if="error" :message="error" />
    <StockTable v-else :rows="rows" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchTopStocks } from '../services/api'
import LoadingState from '../components/LoadingState.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import StockTable from '../components/StockTable.vue'

const rows = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const res = await fetchTopStocks()
    rows.value = res.data
  } catch (e) {
    error.value = 'Không thể tải danh sách cơ hội'
  } finally {
    loading.value = false
  }
})
</script>
