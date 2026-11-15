<script setup lang="ts">
import { toast } from 'vue-sonner'

import ConversationPanel from '@/components/console/ConversationPanel.vue'
import TicketList from '@/components/console/TicketList.vue'
import { useInboxStore } from '@/stores/inbox'

const inbox = useInboxStore()

function acknowledge(id: string) {
  if (inbox.acknowledge(id)) toast.success('已确认接管，机器人会暂停自动回复')
}

function resolve(id: string) {
  if (inbox.resolve(id)) toast.success('已标记解决，客户再发消息时机器人恢复接待')
}
</script>

<template>
  <div
    class="grid h-auto grid-cols-1 gap-4 lg:h-[calc(100svh-7rem)] lg:min-h-[520px] lg:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]"
  >
    <TicketList
      :tickets="inbox.visible"
      :selected-id="inbox.selectedId"
      :tab="inbox.tab"
      :counts="inbox.counts"
      @update:tab="inbox.setTab"
      @select="inbox.select"
    />
    <ConversationPanel :ticket="inbox.selected" :thread="inbox.thread" @acknowledge="acknowledge" @resolve="resolve" />
  </div>
</template>
