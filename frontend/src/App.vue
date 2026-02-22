<template>
  <div class="min-h-screen bg-gradient-to-br from-white via-slate-50 to-slate-100">
    <header class="px-6 py-4 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div class="max-w-6xl mx-auto flex items-center justify-between">
        <div class="text-xl font-semibold font-display">CycleMaster</div>
        <nav class="flex gap-4 text-sm">
          <RouterLink to="/" class="hover:text-sky">Tổng quan</RouterLink>
          <RouterLink to="/opportunities" class="hover:text-sky">Cơ hội nổi bật</RouterLink>
          <RouterLink to="/alerts" class="hover:text-sky">Cảnh báo rủi ro</RouterLink>
          <RouterLink to="/backtest" class="hover:text-sky">Kiểm định chiến lược</RouterLink>
        </nav>
      </div>
    </header>
    <main class="max-w-6xl mx-auto px-6 py-6">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
</script>
