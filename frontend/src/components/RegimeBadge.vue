<template>
  <span :class="badgeClass" class="px-2 py-1 text-xs rounded-full font-semibold">
    {{ displayText }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  regime: { type: String, required: true },
  score: { type: Number, default: null }
})

const badgeClass = computed(() => {
  switch (props.regime) {
    case 'MARKUP':
      return props.score !== null && props.score >= 75 ? 'bg-mint/40 text-mint' : 'bg-mint/20 text-mint'
    case 'ACCUMULATION':
    case 'ACCUMULATION_STRONG':
      return 'bg-sky/40 text-sky'
    case 'ACCUMULATION_WEAK':
      return 'bg-sky/20 text-sky'
    case 'DISTRIBUTION':
      return 'bg-amber/20 text-amber'
    case 'MARKDOWN':
      return 'bg-rose/20 text-rose'
    case 'NEUTRAL':
      return 'bg-slate-200 text-slate-600'
    case 'NO_DATA':
      return 'bg-slate-100 text-slate-500'
    case 'LOW_LIQUIDITY':
      return 'bg-slate-100 text-slate-500'
    default:
      return 'bg-slate-200 text-slate-700'
  }
})

const displayText = computed(() => {
  switch (props.regime) {
    case 'ACCUMULATION':
    case 'ACCUMULATION_STRONG':
    case 'ACCUMULATION_WEAK':
      return 'Tích lũy'
    case 'MARKUP':
      return 'Đẩy giá'
    case 'DISTRIBUTION':
      return 'Phân phối'
    case 'MARKDOWN':
      return 'Đè giá'
    case 'NEUTRAL':
      return 'Trung lập'
    case 'NO_DATA':
      return 'Chưa quét'
    case 'LOW_LIQUIDITY':
      return 'Thanh khoản thấp'
    default:
      return props.regime
  }
})
</script>
