<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppShell from '../layouts/AppShell.vue'
import AgentChatPanel from '../components/AgentChatPanel.vue'
import {
  getDashboardOverview,
  getProducts,
  getPendingHandoffs,
  getRecentConversations,
  acknowledgeHandoff,
  type DashboardOverview,
  type Product,
  type RecentConversation,
} from '../services/workflow'
import type { AgentWorkflowData } from '../services/agent'

const overview = ref<DashboardOverview>({
  total_conversations: 0,
  failed_requests: 0,
  human_handoffs: 0,
  pending_handoffs: 0,
  resolution_rate: 100,
  top_intent: '暂无数据',
  languages: [],
  intents: [],
  started_at: '',
})
const products = ref<Product[]>([])
const recentConversations = ref<RecentConversation[]>([])
const pendingHandoffs = ref<RecentConversation[]>([])
const loadingOverview = ref(true)
const overviewError = ref('')
const handoffError = ref('')
const acknowledgingHandoffId = ref('')
const lastWorkflow = ref<AgentWorkflowData | null>(null)

const statusText = computed(() => {
  if (loadingOverview.value) {
    return '正在连接服务'
  }

  if (lastWorkflow.value?.source?.startsWith('astrbot')) {
    return 'AstrBot 模型在线'
  }

  return '本地演示策略在线'
})

async function refreshOverview() {
  try {
    const response = await getDashboardOverview()
    overview.value = response.data
    overviewError.value = ''
  } catch {
    overviewError.value = '看板数据暂不可用，Agent 对话仍可继续。'
  } finally {
    loadingOverview.value = false
  }
}

async function loadProducts() {
  try {
    const response = await getProducts()
    products.value = response.data
  } catch {
    products.value = []
  }
}

async function refreshRecentConversations() {
  try {
    const response = await getRecentConversations()
    recentConversations.value = response.data
  } catch {
    recentConversations.value = []
  }
}

async function refreshPendingHandoffs() {
  try {
    const response = await getPendingHandoffs()
    pendingHandoffs.value = response.data
  } catch {
    pendingHandoffs.value = []
  }
}

async function acknowledge(recordId: string) {
  acknowledgingHandoffId.value = recordId
  handoffError.value = ''
  try {
    await acknowledgeHandoff(recordId)
    await Promise.all([refreshOverview(), refreshPendingHandoffs(), refreshRecentConversations()])
  } catch {
    handoffError.value = '确认接管失败，请刷新后重试。'
  } finally {
    acknowledgingHandoffId.value = ''
  }
}

function handleWorkflowComplete(result: AgentWorkflowData) {
  lastWorkflow.value = result
  void Promise.all([refreshOverview(), refreshRecentConversations(), refreshPendingHandoffs()])
}

onMounted(() => {
  void Promise.all([refreshOverview(), loadProducts(), refreshRecentConversations(), refreshPendingHandoffs()])
})

function formatTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '刚刚'
    : new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(date)
}

function sourceLabel(source: AgentWorkflowData['source']) {
  if (source === 'astrbot+human-handoff') {
    return '模型回复 · 已转人工'
  }
  if (source === 'astrbot') {
    return 'AstrBot 模型'
  }
  return '本地演示策略'
}

function ratio(count: number, total: number) {
  return Math.round((count / Math.max(total, 1)) * 100)
}
</script>

<template>
  <AppShell>
    <div class="workspace-stack">
      <section class="intro" aria-labelledby="workspace-title">
        <div class="intro-topline">
          <div class="placeholder-badge">AI 智能体 · 跨境服务闭环</div>
          <span class="service-pill"><i></i>{{ statusText }}</span>
        </div>
        <h2 id="workspace-title">跨境服务智能体</h2>
        <p>面向中小跨境商家的多语言客服工作台：自动理解客户意图、检索商品资料、生成双语话术，并在复杂售后问题上提醒人工接管。</p>
      </section>
      <section class="metric-grid" aria-label="服务数据概览">
        <article class="metric-card">
          <span>累计咨询</span>
          <strong>{{ overview.total_conversations }}</strong>
          <small>Agent 已处理会话</small>
        </article>
        <article class="metric-card">
          <span>自动解决率</span>
          <strong>{{ overview.resolution_rate }}<em>%</em></strong>
          <small>常规咨询自动完成</small>
        </article>
        <article class="metric-card metric-card--warning">
          <span>人工接管</span>
          <strong>{{ overview.pending_handoffs }}</strong>
          <small>等待商家接管</small>
        </article>
        <article class="metric-card metric-card--accent">
          <span>热门意图</span>
          <strong class="metric-card__text">{{ overview.top_intent }}</strong>
          <small>实时统计</small>
        </article>
      </section>

      <div v-if="overviewError" class="overview-error">{{ overviewError }}</div>

      <section class="handoff-card">
        <div class="insight-card__heading">
          <div><span class="section-kicker">HUMAN IN THE LOOP</span><h3>人工接管队列</h3></div>
          <span class="handoff-count">{{ pendingHandoffs.length }} 项待处理</span>
        </div>
        <p v-if="handoffError" class="handoff-error">{{ handoffError }}</p>
        <div v-if="pendingHandoffs.length" class="handoff-list">
          <article v-for="item in pendingHandoffs" :key="item.id" class="handoff-row">
            <div class="handoff-row__copy">
              <div><strong>{{ item.intent_label }}</strong><span>{{ item.language_label }}</span><time>{{ formatTime(item.created_at) }}</time></div>
              <p>{{ item.message }}</p>
              <small>{{ item.handoff_reason || item.merchant_summary }}</small>
            </div>
            <button type="button" :disabled="acknowledgingHandoffId === item.id" @click="acknowledge(item.id)">
              {{ acknowledgingHandoffId === item.id ? '处理中…' : '确认接管' }}
            </button>
          </article>
        </div>
        <div v-else class="handoff-empty">当前没有待接管事项。复杂售后或退款咨询会进入此队列。</div>
      </section>

      <div class="workspace-main-grid">
        <AgentChatPanel @workflow-complete="handleWorkflowComplete" />
        <aside class="insight-column" aria-label="Agent 流程看板">
          <section class="insight-card">
            <div class="insight-card__heading">
              <div>
                <span class="section-kicker">PROCESS MONITOR</span>
                <h3>服务流程监控</h3>
              </div>
              <span class="live-label"><i></i>LIVE</span>
            </div>
            <div class="flow-line">
              <div class="flow-node flow-node--active"><span>01</span><strong>理解</strong><small>语言 / 意图</small></div>
              <div class="flow-connector"></div>
              <div class="flow-node"><span>02</span><strong>检索</strong><small>商品知识库</small></div>
              <div class="flow-connector"></div>
              <div class="flow-node"><span>03</span><strong>交付</strong><small>回复 / 摘要</small></div>
            </div>
            <div v-if="lastWorkflow" class="last-event">
              <div class="last-event__title">最近一次处理</div>
              <div class="last-event__row"><span>意图</span><strong>{{ lastWorkflow.intent_label }}</strong></div>
              <div class="last-event__row"><span>语言</span><strong>{{ lastWorkflow.language_label }}</strong></div>
              <div class="last-event__row"><span>执行来源</span><strong>{{ sourceLabel(lastWorkflow.source) }}</strong></div>
              <div class="last-event__row"><span>商品匹配</span><strong>{{ lastWorkflow.matched_product }}</strong></div>
              <div class="last-event__row"><span>结果</span><strong>{{ lastWorkflow.needs_human ? '已转人工' : '自动完成' }}</strong></div>
            </div>
            <div v-else class="empty-event">发送一条咨询后，这里会显示本次 Agent 的处理结果。</div>
          </section>

          <section class="insight-card">
            <div class="insight-card__heading">
              <div>
                <span class="section-kicker">KNOWLEDGE BASE</span>
                <h3>商品资料库</h3>
              </div>
              <span class="count-label">{{ products.length }} 个商品</span>
            </div>
            <div class="product-list">
              <div v-for="product in products" :key="product.id" class="product-row">
                <div class="product-icon">{{ product.name.slice(0, 1) }}</div>
                <div class="product-copy"><strong>{{ product.name }}</strong><span>{{ product.category }} · ${{ product.price_usd.toFixed(2) }}</span></div>
                <span class="stock-label">库存 {{ product.stock }}</span>
              </div>
              <div v-if="!products.length" class="empty-event">正在加载商品资料…</div>
            </div>
          </section>
        </aside>
      </div>

      <section v-if="overview.intents.length" class="intent-card">
        <div class="insight-card__heading">
          <div><span class="section-kicker">ANALYTICS</span><h3>咨询意图分布</h3></div>
          <span class="count-label">累计 {{ overview.total_conversations }} 次</span>
        </div>
        <div class="intent-bars">
          <div v-for="item in overview.intents" :key="item.code" class="intent-bar-row">
            <span>{{ item.label }}</span>
            <div class="intent-track"><i :style="{ width: `${Math.max(8, (item.count / Math.max(overview.total_conversations, 1)) * 100)}%` }"></i></div>
            <strong>{{ item.count }}</strong>
          </div>
        </div>
      </section>

      <section v-if="overview.languages.length" class="language-card">
        <div class="insight-card__heading">
          <div><span class="section-kicker">LANGUAGE COVERAGE</span><h3>客户语言分布</h3></div>
          <span class="count-label">支持多语言接待</span>
        </div>
        <div class="language-grid">
          <div v-for="item in overview.languages" :key="item.code" class="language-row">
            <div class="language-row__meta"><strong>{{ item.label }}</strong><span>{{ item.count }} 次 · {{ ratio(item.count, overview.total_conversations) }}%</span></div>
            <div class="language-track"><i :style="{ width: `${Math.max(8, ratio(item.count, overview.total_conversations))}%` }"></i></div>
          </div>
        </div>
      </section>

      <section class="archive-card">
        <div class="insight-card__heading">
          <div><span class="section-kicker">CONVERSATION ARCHIVE</span><h3>最近咨询归档</h3></div>
          <span class="count-label">最近 {{ recentConversations.length }} 条</span>
        </div>
        <div v-if="recentConversations.length" class="archive-list">
          <article v-for="conversation in recentConversations" :key="conversation.id" class="archive-row">
            <div class="archive-row__status" :class="{ 'archive-row__status--handoff': conversation.needs_human && !conversation.human_acknowledged }">
              {{ conversation.needs_human ? (conversation.human_acknowledged ? '已接管' : '待接管') : '已完成' }}
            </div>
            <div class="archive-row__body">
              <div class="archive-row__meta">
                <strong>{{ conversation.intent_label }}</strong>
                <span>{{ conversation.language_label }}</span>
                <time>{{ formatTime(conversation.created_at) }}</time>
              </div>
              <p class="archive-row__message">{{ conversation.message }}</p>
              <div class="archive-row__summary">{{ conversation.merchant_summary }}</div>
            </div>
            <div class="archive-row__reply">{{ conversation.reply }}</div>
          </article>
        </div>
        <div v-else class="archive-empty">还没有已归档的咨询。发送一条测试消息后，摘要会显示在这里。</div>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.workspace-stack {
  display: grid;
  gap: 20px;
}

.intro {
  max-width: 840px;
  margin: 0 auto;
  align-self: stretch;
}

.intro-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.placeholder-badge {
  display: inline-flex;
  padding: 6px 10px;
  border-radius: 999px;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  font-size: 12px;
  font-weight: 600;
}

h2 {
  margin: 18px 0 10px;
  color: var(--color-text);
  font-size: clamp(26px, 4vw, 38px);
  line-height: 1.2;
}

p {
  max-width: 620px;
  margin: 0;
  color: var(--color-text-secondary);
  line-height: 1.8;
}

.service-pill,
.live-label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #027a48;
  font-size: 11px;
  font-weight: 700;
}

.service-pill i,
.live-label i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #12b76a;
  box-shadow: 0 0 0 4px #ecfdf3;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.metric-card {
  display: flex;
  min-height: 124px;
  flex-direction: column;
  justify-content: space-between;
  padding: 18px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: #fff;
  box-shadow: var(--shadow-sm);
}

.metric-card > span,
.metric-card small {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.metric-card strong {
  color: var(--color-text);
  font-size: 30px;
  line-height: 1;
}

.metric-card strong em {
  margin-left: 2px;
  color: var(--color-primary);
  font-size: 15px;
  font-style: normal;
}

.metric-card__text {
  font-size: 21px !important;
}

.metric-card--warning strong { color: #b54708; }
.metric-card--accent { background: linear-gradient(135deg, #eff6ff, #fff); }

.overview-error {
  padding: 10px 14px;
  border-radius: 10px;
  color: #b54708;
  background: #fffaeb;
  font-size: 12px;
}

.workspace-main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(300px, .75fr);
  gap: 20px;
  align-items: start;
}

.insight-column {
  display: grid;
  gap: 20px;
}

.insight-card,
.handoff-card,
.intent-card,
.archive-card {
  padding: 20px;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  background: #fff;
  box-shadow: var(--shadow-sm);
}

.insight-card__heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.section-kicker {
  color: var(--color-primary);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .08em;
}

h3 {
  margin: 5px 0 0;
  color: var(--color-text);
  font-size: 17px;
}

.count-label {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.flow-line {
  display: flex;
  align-items: center;
  margin: 24px 0 18px;
}

.flow-node {
  display: flex;
  min-width: 70px;
  flex-direction: column;
  gap: 2px;
}

.flow-node > span { color: #98a2b3; font-size: 10px; font-weight: 700; }
.flow-node strong { color: var(--color-text); font-size: 13px; }
.flow-node small { color: var(--color-text-secondary); font-size: 10px; }
.flow-node--active strong { color: var(--color-primary); }
.flow-connector { height: 1px; flex: 1; margin: 0 8px; background: #d0d5dd; }

.last-event {
  display: grid;
  gap: 8px;
  padding: 12px;
  border-radius: 10px;
  background: #f8fafc;
}

.last-event__title { color: var(--color-text-secondary); font-size: 11px; }
.last-event__row { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; }
.last-event__row span { color: var(--color-text-secondary); }
.last-event__row strong { color: var(--color-text); }
.empty-event { color: var(--color-text-secondary); font-size: 12px; line-height: 1.7; }

.product-list { display: grid; gap: 10px; margin-top: 18px; }
.product-row { display: flex; align-items: center; gap: 9px; min-width: 0; }
.product-icon { display: grid; width: 30px; height: 30px; flex: 0 0 30px; place-items: center; border-radius: 9px; color: var(--color-primary); background: var(--color-primary-soft); font-size: 13px; font-weight: 700; }
.product-copy { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 2px; }
.product-copy strong { overflow: hidden; color: var(--color-text); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.product-copy span, .stock-label { color: var(--color-text-secondary); font-size: 10px; }
.stock-label { flex: 0 0 auto; }

.intent-card { display: grid; gap: 18px; }
.intent-bars { display: grid; gap: 12px; }
.intent-bar-row { display: grid; grid-template-columns: 70px 1fr 24px; align-items: center; gap: 10px; color: var(--color-text-secondary); font-size: 12px; }
.intent-track { height: 7px; overflow: hidden; border-radius: 999px; background: #eef2f6; }
.intent-track i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #2563eb, #60a5fa); }
.intent-bar-row strong { color: var(--color-text); font-size: 12px; text-align: right; }

.language-card { display: grid; gap: 18px; padding: 20px; border: 1px solid var(--color-border); border-radius: 16px; background: #fff; box-shadow: var(--shadow-sm); }
.language-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.language-row { display: grid; gap: 8px; }
.language-row__meta { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: var(--color-text-secondary); font-size: 11px; }
.language-row__meta strong { color: var(--color-text); font-size: 12px; }
.language-track { height: 8px; overflow: hidden; border-radius: 999px; background: #eef2f6; }
.language-track i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #7c3aed, #a78bfa); }

.archive-card { display: grid; gap: 16px; }
.archive-list { display: grid; }
.archive-row { display: grid; grid-template-columns: 74px minmax(200px, .9fr) minmax(180px, .8fr); gap: 14px; align-items: start; padding: 14px 0; border-top: 1px solid #f0f2f5; }
.archive-row__status { justify-self: start; padding: 5px 8px; border-radius: 999px; color: #027a48; background: #ecfdf3; font-size: 10px; font-weight: 700; }
.archive-row__status--handoff { color: #b54708; background: #fffaeb; }
.archive-row__body { min-width: 0; }
.archive-row__meta { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; color: var(--color-text-secondary); font-size: 10px; }
.archive-row__meta strong { color: var(--color-text); font-size: 11px; }
.archive-row__meta time { margin-left: auto; }
.archive-row__message { overflow: hidden; margin: 6px 0 4px; color: var(--color-text); font-size: 12px; line-height: 1.5; text-overflow: ellipsis; }
.archive-row__summary { color: var(--color-text-secondary); font-size: 10px; line-height: 1.5; }
.archive-row__reply { padding: 9px 10px; border-radius: 8px; color: #344054; background: #f8fafc; font-size: 11px; line-height: 1.6; }
.archive-empty { padding: 18px; border-radius: 10px; color: var(--color-text-secondary); background: #f8fafc; font-size: 12px; text-align: center; }
.handoff-card { display: grid; gap: 14px; padding: 20px; border: 1px solid #fedf89; border-radius: 16px; background: linear-gradient(145deg, #fffdf5, #fff); box-shadow: var(--shadow-sm); }
.handoff-count { padding: 5px 8px; border-radius: 999px; color: #b54708; background: #fffaeb; font-size: 10px; font-weight: 700; }
.handoff-list { display: grid; gap: 10px; }
.handoff-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 12px; border: 1px solid #f2e6c8; border-radius: 10px; background: #fff; }
.handoff-row__copy { min-width: 0; flex: 1; }
.handoff-row__copy > div { display: flex; align-items: center; gap: 8px; color: var(--color-text-secondary); font-size: 10px; }
.handoff-row__copy strong { color: #b54708; font-size: 12px; }
.handoff-row__copy time { margin-left: auto; }
.handoff-row__copy p { margin: 6px 0 3px; color: var(--color-text); font-size: 12px; }
.handoff-row__copy small { color: var(--color-text-secondary); font-size: 10px; }
.handoff-row button { flex: 0 0 auto; padding: 8px 11px; border: 0; border-radius: 8px; color: #fff; background: #d97706; cursor: pointer; font-size: 11px; font-weight: 700; }
.handoff-row button:disabled { cursor: wait; opacity: .65; }
.handoff-empty { padding: 14px; border-radius: 9px; color: var(--color-text-secondary); background: rgb(255 255 255 / 75%); font-size: 12px; text-align: center; }
.handoff-error { margin: 0; color: #b42318; font-size: 11px; }

@media (max-width: 1100px) {
  .workspace-main-grid { grid-template-columns: 1fr; }
  .insight-column { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 700px) {
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .insight-column { grid-template-columns: 1fr; }
  .language-grid { grid-template-columns: 1fr; }
  .intro-topline { align-items: flex-start; flex-direction: column; }
  .archive-row { grid-template-columns: 1fr; gap: 8px; }
  .archive-row__meta time { margin-left: 0; }
  .handoff-row { align-items: flex-start; flex-direction: column; }
}
</style>
