<template>
  <div class="overflow-hidden rounded-xl border border-slate-200 bg-white">
    <table class="min-w-full text-sm">
      <thead class="bg-slate-100 text-slate-600">
        <tr>
          <th class="text-left p-3">Mã</th>
          <th class="text-left p-3">Chu kỳ</th>
          <th class="text-left p-3">Điểm</th>
          <th class="text-left p-3">Vùng mua</th>
          <th class="text-left p-3">Chốt lời</th>
          <th class="text-left p-3">R:R</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.symbol" class="border-t border-slate-100">
          <td class="p-3">
            <RouterLink :to="`/stocks/${row.symbol}`" class="text-sky">{{ row.symbol }}</RouterLink>
          </td>
          <td class="p-3"><RegimeBadge :regime="row.regime" /></td>
          <td class="p-3">{{ row.score.toFixed(1) }}</td>
          <td class="p-3">{{ row.buy_zone }}</td>
          <td class="p-3">{{ row.take_profit }}</td>
          <td class="p-3">{{ row.risk_reward.toFixed(2) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import RegimeBadge from './RegimeBadge.vue'

defineProps({
  rows: { type: Array, default: () => [] }
})
</script>
