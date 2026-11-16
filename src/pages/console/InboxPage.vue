<script setup lang="ts">
import { CircleAlert } from '@lucide/vue'
import { toast } from 'vue-sonner'

import { toApiError } from '@/api/errors'
import ConversationPanel from '@/components/console/ConversationPanel.vue'
import TicketList from '@/components/console/TicketList.vue'
import { useInboxStore } from '@/stores/inbox'

// The console layout polls the tickets every 10 s; this page only acts on them.
const inbox = useInboxStore()

async function acknowledge(id: string) {
  try {
    await inbox.acknowledge(id)
    toast.success('已确认接管，机器人会暂停自动回复')
  } catch (error) {
    toast.error(`确认接管失败：${toApiError(error).message}`)
  }
}

async function resolve(id: string) {
  try {
    await inbox.resolve(id)
    toast.success('已标记解决，客户再发消息时机器人恢复接待')
  } catch (error) {
    toast.error(`标记解决失败：${toApiError(error).message}`)
  }
}
</script>

<template>
  <div
    v-if="inbox.error && inbox.error.code !== 'UNAUTHORIZED'"
    class="mb-4 flex items-start gap-2.5 rounded-xl border bg-card px-4 py-3 text-sm"
    role="alert"
  >
    <CircleAlert class="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
    <p class="text-muted-foreground">
      工单列表刷新失败：{{ inbox.error.message }}<template v-if="inbox.loaded">（显示的是上一次成功获取的数据）</template>
    </p>
  </div>
  <div
    class="grid h-auto grid-cols-1 gap-4 lg:h-[calc(100svh-7rem)] lg:min-h-[520px] lg:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]"
  >
    <TicketList
      :tickets="inbox.visible"
      :selected-id="inbox.selectedId"
      :tab="inbox.tab"
      :counts="inbox.counts"
      :loading="!inbox.loaded && !inbox.error"
      :failed="!inbox.loaded && Boolean(inbox.error)"
      @update:tab="inbox.setTab"
      @select="inbox.select"
    />
    <ConversationPanel
      :ticket="inbox.selected"
      :thread="inbox.thread"
      :loading="inbox.loadingThread"
      :error="inbox.threadError"
      :busy="inbox.pendingAction === inbox.selectedId"
      @acknowledge="acknowledge"
      @resolve="resolve"
      @reload="inbox.refresh"
    />
  </div>
</template>
