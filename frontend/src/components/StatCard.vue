<template>
  <div class="p-4 bg-white rounded-xl border border-slate-200 shadow-sm">
    <div class="text-xs uppercase text-slate-500">{{ label }}</div>
    <div class="text-lg font-semibold">{{ value }}</div>
    <div v-if="hint" class="text-xs text-slate-500">{{ hint }}</div>
  </div>
</template>

<script setup>
defineProps({
  label: String,
  value: [String, Number],
  hint: String
})
</script>
