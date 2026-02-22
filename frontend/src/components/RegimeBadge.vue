<template>
  <span :class="badgeClass" class="px-2 py-1 text-xs rounded-full font-semibold">
    {{ regime }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  regime: { type: String, required: true }
})

const badgeClass = computed(() => {
  switch (props.regime) {
    case 'MARKUP':
      return 'bg-mint/20 text-mint'
    case 'ACCUMULATION':
      return 'bg-sky/20 text-sky'
    case 'DISTRIBUTION':
      return 'bg-amber/20 text-amber'
    case 'MARKDOWN':
      return 'bg-rose/20 text-rose'
    default:
      return 'bg-slate-200 text-slate-700'
  }
})
</script>
