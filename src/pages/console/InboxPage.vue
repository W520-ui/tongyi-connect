<script setup lang="ts">
import { useMessage } from 'naive-ui'

import ConversationPanel from '../../components/console/ConversationPanel.vue'
import TicketList from '../../components/console/TicketList.vue'
import { useInboxStore } from '../../stores/inbox'

const inbox = useInboxStore()
const message = useMessage()

function acknowledge(id: string) {
  if (inbox.acknowledge(id)) message.success('已确认接管，机器人会暂停自动回复')
}

function resolve(id: string) {
  if (inbox.resolve(id)) message.success('已标记解决，客户再发消息时机器人恢复接待')
}
</script>

<template>
  <div class="inbox">
    <TicketList
      :tickets="inbox.visible"
      :selected-id="inbox.selectedId"
      :tab="inbox.tab"
      :counts="inbox.counts"
      @update:tab="inbox.setTab"
      @select="inbox.select"
    />
    <ConversationPanel
      :ticket="inbox.selected"
      :thread="inbox.thread"
      @acknowledge="acknowledge"
      @resolve="resolve"
    />
  </div>
</template>

<style scoped>
.inbox {
  display: grid;
  height: calc(100vh - 64px - 50px);
  min-height: 520px;
  grid-template-columns: minmax(300px, 380px) minmax(0, 1fr);
  gap: 16px;
}

@media (max-width: 960px) {
  .inbox {
    height: auto;
    grid-template-columns: 1fr;
  }
}
</style>
