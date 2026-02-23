<template>
  <span :class="badgeClass" class="px-2 py-1 text-xs rounded-full font-semibold">
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: '' }
})

const label = computed(() => {
  switch (props.status) {
    case 'VALID':
      return 'Valid'
    case 'WEAK':
      return 'Weak'
    case 'INVALID':
      return 'Invalid'
    case 'LOW_LIQUIDITY':
      return 'Low Liquidity'
    case 'NO_SETUP':
      return 'No Setup'
    default:
      return 'N/A'
  }
})

const badgeClass = computed(() => {
  switch (props.status) {
    case 'VALID':
      return 'bg-mint/30 text-mint'
    case 'WEAK':
      return 'bg-amber/20 text-amber'
    case 'INVALID':
      return 'bg-rose/20 text-rose'
    case 'LOW_LIQUIDITY':
      return 'bg-slate-100 text-slate-500'
    case 'NO_SETUP':
      return 'bg-slate-100 text-slate-500'
    default:
      return 'bg-slate-100 text-slate-500'
  }
})
</script>
