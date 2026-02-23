<template>
  <div class="overflow-hidden rounded-xl border border-slate-200 bg-white">
    <table class="min-w-full text-sm">
      <thead class="bg-slate-100 text-slate-600">
        <tr>
          <th class="text-left p-3">Mã</th>
          <th class="text-left p-3">Chu kỳ</th>
          <th class="text-left p-3">Điểm</th>
          <th class="text-left p-3">Giá hiện tại (nghìn đ)</th>
          <th class="text-left p-3">Vùng mua (nghìn đ)</th>
          <th class="text-left p-3">Chốt lời (nghìn đ)</th>
          <th class="text-left p-3">Cắt lỗ (nghìn đ)</th>
          <th class="text-left p-3">% Upside</th>
          <th class="text-left p-3">% Downside</th>
          <th class="text-left p-3">Thanh khoản</th>
          <th class="text-left p-3">Trạng thái</th>
          <th class="text-left p-3">Đồng phối</th>
          <th class="text-left p-3">Tier</th>
          <th class="text-left p-3">Xếp hạng</th>
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
          <td class="p-3">{{ formatMoney(row.last_close) }}</td>
          <td class="p-3">{{ formatZone(row.buy_zone) }}</td>
          <td class="p-3">{{ formatMoney(row.take_profit) }}</td>
          <td class="p-3">{{ formatMoney(row.stop_loss) }}</td>
          <td class="p-3">{{ formatPercent(getUpside(row)) }}</td>
          <td class="p-3">{{ formatPercent(getDownside(row)) }}</td>
          <td class="p-3"><LiquidityBadge :score="row.liquidity_score" /></td>
          <td class="p-3"><SetupStatusBadge :status="row.setup_status" /></td>
          <td class="p-3"><MarketAlignmentBadge :alignment="row.market_alignment" /></td>
          <td class="p-3">{{ row.setup_tier || '-' }}</td>
          <td class="p-3">{{ idx + 1 }}</td>
          <td class="p-3">{{ formatRisk(row.risk_reward) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import RegimeBadge from './RegimeBadge.vue'
import LiquidityBadge from './LiquidityBadge.vue'
import SetupStatusBadge from './SetupStatusBadge.vue'
import MarketAlignmentBadge from './MarketAlignmentBadge.vue'

defineProps({
  rows: { type: Array, default: () => [] }
})

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

const parseZoneMid = (zone) => {
  if (!zone || zone === '-') return null
  const parts = String(zone).split('-')
  if (parts.length !== 2) return null
  const a = Number(parts[0])
  const b = Number(parts[1])
  if (Number.isNaN(a) || Number.isNaN(b)) return null
  return (a + b) / 2
}

const getUpside = (row) => {
  const entry = parseZoneMid(row.buy_zone)
  const tp = Number(row.take_profit)
  if (!entry || Number.isNaN(tp)) return null
  return ((tp - entry) / entry) * 100
}

const getDownside = (row) => {
  const entry = parseZoneMid(row.buy_zone)
  const sl = Number(row.stop_loss)
  if (!entry || Number.isNaN(sl)) return null
  return ((entry - sl) / entry) * 100
}

const formatPercent = (value) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return `${value.toFixed(1)}%`
}

const formatRisk = (value) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return Number(value).toFixed(2)
}
</script>
