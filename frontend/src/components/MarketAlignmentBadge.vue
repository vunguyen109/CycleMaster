<template>
  <span :class="badgeClass" class="px-2 py-1 text-xs rounded-full font-semibold">
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  alignment: { type: String, default: '' }
})

const label = computed(() => {
  switch (props.alignment) {
    case 'ALIGNED':
      return 'Aligned'
    case 'MISALIGNED':
      return 'Misaligned'
    case 'NEUTRAL':
      return 'Neutral'
    default:
      return 'N/A'
  }
})

const badgeClass = computed(() => {
  switch (props.alignment) {
    case 'ALIGNED':
      return 'bg-mint/30 text-mint'
    case 'MISALIGNED':
      return 'bg-rose/20 text-rose'
    case 'NEUTRAL':
      return 'bg-slate-100 text-slate-500'
    default:
      return 'bg-slate-100 text-slate-500'
  }
})
</script>
