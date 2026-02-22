<template>
  <div class="p-3 bg-rose-50 text-rose-700 rounded-lg border border-rose-200">
    {{ message }}
  </div>
</template>

<script setup>
defineProps({
  message: { type: String, required: true }
})
</script>
