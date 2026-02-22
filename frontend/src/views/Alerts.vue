<template>
  <div>
    <h2 class="text-lg font-semibold mb-4">Cảnh báo phân phối</h2>
    <LoadingState v-if="loading" />
    <ErrorBanner v-else-if="error" :message="error" />
    <div v-else class="grid gap-3">
      <div v-for="a in alerts" :key="a.symbol" class="p-4 bg-white rounded-xl border border-slate-200">
        <div class="flex items-center justify-between">
          <div class="font-semibold">{{ a.symbol }}</div>
          <RegimeBadge :regime="a.regime" />
        </div>
        <div class="text-sm text-slate-500">Độ tin cậy: {{ a.confidence.toFixed(1) }}%</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchAlerts } from '../services/api'
import LoadingState from '../components/LoadingState.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import RegimeBadge from '../components/RegimeBadge.vue'

const alerts = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const res = await fetchAlerts()
    alerts.value = res.data
  } catch (e) {
    error.value = 'Không thể tải cảnh báo'
  } finally {
    loading.value = false
  }
})
</script>
