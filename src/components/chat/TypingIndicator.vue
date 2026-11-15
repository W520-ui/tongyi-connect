<script setup lang="ts">
import { Bot } from 'lucide-vue-next'
import { NIcon } from 'naive-ui'

defineProps<{ label: string }>()
</script>

<template>
  <div class="typing" role="status">
    <div class="avatar" aria-hidden="true"><NIcon :size="16" :component="Bot" /></div>
    <div class="dots" :aria-label="label"><i /><i /><i /></div>
  </div>
</template>

<style scoped>
.typing {
  display: flex;
  align-items: center;
  gap: 10px;
}

.avatar {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 1px solid rgba(15, 118, 110, 0.14);
  border-radius: 50%;
  color: var(--brand);
  background: var(--brand-soft);
}

.dots {
  display: inline-flex;
  gap: 5px;
  padding: 14px 16px;
  border-radius: 18px 18px 18px 6px;
  background: #f1f5f4;
}

.dots i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #94a3b8;
  animation: bounce 1.2s ease-in-out infinite;
}

.dots i:nth-child(2) {
  animation-delay: 0.15s;
}

.dots i:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes bounce {
  0%,
  60%,
  100% {
    opacity: 0.45;
    transform: translateY(0);
  }

  30% {
    opacity: 1;
    transform: translateY(-4px);
  }
}
</style>
