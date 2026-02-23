<template>
  <div class="p-4 bg-white rounded-xl border border-slate-200">
    <div class="text-sm font-semibold mb-2">Chu kỳ cổ phiếu</div>
    <div class="w-full overflow-x-auto">
      <svg viewBox="0 0 900 320" class="w-full h-72">
        <path
          d="M20,260 C120,330 230,310 300,230 C360,160 420,70 520,60 C640,50 690,170 720,220 C760,280 820,300 880,290"
          fill="none"
          stroke="#1d4ed8"
          stroke-width="6"
          stroke-linecap="round"
        />
        <line x1="360" y1="250" x2="470" y2="110" stroke="#22c55e" stroke-width="10" />
        <polygon points="470,110 455,118 475,128" fill="#22c55e" />
        <line x1="640" y1="90" x2="710" y2="230" stroke="#ef4444" stroke-width="10" />
        <polygon points="710,230 700,210 690,230" fill="#ef4444" />
        <text x="80" y="210" font-size="20" fill="#0f172a">Tích lũy</text>
        <text x="80" y="235" font-size="16" fill="#64748b">(Accumulation)</text>
        <text x="320" y="140" font-size="20" fill="#0f172a">Đẩy giá</text>
        <text x="320" y="165" font-size="16" fill="#64748b">(Mark-Up)</text>
        <text x="520" y="35" font-size="20" fill="#0f172a">Phân phối</text>
        <text x="520" y="60" font-size="16" fill="#64748b">(Distribution)</text>
        <text x="700" y="150" font-size="20" fill="#0f172a">Đè giá</text>
        <text x="700" y="175" font-size="16" fill="#64748b">(Decline)</text>
      </svg>
    </div>
  </div>
</template>
