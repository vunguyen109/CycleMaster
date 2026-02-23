<template>
  <span :class="badgeClass" class="px-2 py-1 text-xs rounded-full font-semibold">
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  score: { type: Number, default: null }
})

const label = computed(() => {
  if (props.score === null || props.score === undefined) return 'N/A'
  if (props.score >= 8) return 'High'
  if (props.score >= 4) return 'Medium'
  return 'Low'
})

const badgeClass = computed(() => {
  if (props.score === null || props.score === undefined) return 'bg-slate-100 text-slate-500'
  if (props.score >= 8) return 'bg-mint/30 text-mint'
  if (props.score >= 4) return 'bg-amber/20 text-amber'
  return 'bg-rose/20 text-rose'
})
</script>
