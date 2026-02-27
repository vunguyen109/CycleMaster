<template>
  <div class="overflow-hidden rounded-xl border border-slate-200 bg-white">
    <table class="min-w-full text-sm">
      <thead class="bg-slate-100 text-slate-600">
        <tr>
          <th class="text-left p-3">Mã</th>
          <th class="text-left p-3">Chu kỳ</th>
          <th class="text-left p-3">Điểm</th>
          <th class="text-left p-3">Trạng thái</th>
          <th class="text-left p-3">Entry</th>
          <th class="text-left p-3">Stop</th>
          <th class="text-left p-3">Target</th>
          <th class="text-left p-3">R:R</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, idx) in rows" :key="row.symbol" class="border-t border-slate-100">
          <td class="p-3">
            <RouterLink :to="`/stocks/${row.symbol}`" class="text-sky">{{ row.symbol }}</RouterLink>
          </td>
          <td class="p-3"><RegimeBadge :regime="row.regime" :score="row.score" /></td>
          <td class="p-3">{{ row.score.toFixed(1) }}</td>
          <td class="p-3"><SetupStatusBadge :status="row.action || row.setup_status" /></td>
          <td class="p-3">{{ formatMoney(row.entry) }}</td>
          <td class="p-3">{{ formatMoney(row.stop) }}</td>
          <td class="p-3">{{ formatMoney(row.target) }}</td>
          <td class="p-3">{{ formatRisk(row.rr) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import RegimeBadge from './RegimeBadge.vue'
import SetupStatusBadge from './SetupStatusBadge.vue'

defineProps({
  rows: { type: Array, default: () => [] }
})

const formatMoney = (value) => {
  if (value === null || value === undefined || value === '-' || value === '') return '-'
  const num = Number(value)
  if (Number.isNaN(num)) return value
  return (num / 1000).toLocaleString('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}


const formatRisk = (value) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return Number(value).toFixed(2)
}
</script>
