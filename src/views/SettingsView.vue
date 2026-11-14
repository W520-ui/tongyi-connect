<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import AppShell from '../layouts/AppShell.vue'
import { getHealth, type HealthStatus } from '../services/workflow'

type ServiceState = 'loading' | 'online' | 'offline'

const serviceState = ref<ServiceState>('loading')
const health = ref<HealthStatus | null>(null)
const errorMessage = ref('')
const apiBase = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')

async function checkHealth() {
  serviceState.value = 'loading'
  errorMessage.value = ''
  try {
    const response = await getHealth()
    health.value = response
    serviceState.value = 'online'
  } catch {
    serviceState.value = 'offline'
    errorMessage.value = '暂时无法连接后端服务，请确认 FastAPI 已启动。'
  }
}

onMounted(() => {
  void checkHealth()
})
</script>

<template>
  <AppShell>
    <div class="settings-stack">
      <section class="settings-hero" aria-labelledby="settings-title">
        <div>
          <span class="section-kicker">SYSTEM STATUS</span>
          <h2 id="settings-title">运行状态与接入说明</h2>
          <p>这里展示通译智联当前的服务连接、Agent 执行策略和演示流程，便于现场快速确认系统是否就绪。</p>
        </div>
        <RouterLink class="back-link" to="/workspace">返回工作台</RouterLink>
      </section>

      <div class="status-grid">
        <article class="status-card">
          <div class="status-card__topline">
            <span class="status-card__label">后端 API</span>
            <span class="state-pill" :class="`state-pill--${serviceState}`">
              <i></i>{{ serviceState === 'loading' ? '检测中' : serviceState === 'online' ? '在线' : '离线' }}
            </span>
          </div>
          <strong>{{ health?.service ?? '通译智联 API' }}</strong>
          <span>{{ health ? `版本 ${health.version}` : errorMessage || '正在检查服务健康状态' }}</span>
          <button type="button" @click="checkHealth">重新检测</button>
        </article>

        <article class="status-card">
          <div class="status-card__topline">
            <span class="status-card__label">Agent 执行</span>
            <span class="state-pill state-pill--ready"><i></i>可用</span>
          </div>
          <strong>多步骤服务流程</strong>
          <span>语言识别 · 意图判断 · 商品检索 · 回复生成</span>
          <small>由自研 Agent 编排模型与工具，服务端统一完成意图识别与归档。</small>
        </article>

        <article class="status-card">
          <div class="status-card__topline">
            <span class="status-card__label">数据归档</span>
            <span class="state-pill state-pill--ready"><i></i>已启用</span>
          </div>
          <strong>SQLite 会话记录</strong>
          <span>摘要、意图、语言和人工接管状态</span>
          <small>服务重启后仍可在工作台看板中查看最近记录。</small>
        </article>
      </div>

      <section class="settings-card">
        <div class="settings-card__heading">
          <div><span class="section-kicker">INTEGRATION</span><h3>服务接入</h3></div>
          <span class="count-label">浏览器不会接触密钥</span>
        </div>
        <div class="config-list">
          <div class="config-row"><span>前端 API 前缀</span><code>{{ apiBase }}</code></div>
          <div class="config-row"><span>健康检查</span><code>{{ apiBase }}/v1/health</code></div>
          <div class="config-row"><span>模型凭证</span><strong>仅由后端环境变量读取</strong></div>
          <div class="config-row"><span>异常处理</span><strong>模型不可用或缺少配置时返回明确错误</strong></div>
        </div>
      </section>

      <section class="settings-card">
        <div class="settings-card__heading">
          <div><span class="section-kicker">DEMO SCRIPT</span><h3>现场演示顺序</h3></div>
          <span class="count-label">约 1 分钟</span>
        </div>
        <ol class="demo-list">
          <li><b>01</b><span>发送英文或西班牙语询价，观察语言和意图标签。</span></li>
          <li><b>02</b><span>查看商品资料命中、价格和配送时效，展示任务拆解。</span></li>
          <li><b>03</b><span>发送售后或退款消息，展示人工接管队列。</span></li>
          <li><b>04</b><span>在工作台查看会话摘要、意图统计和语言分布。</span></li>
        </ol>
        <RouterLink class="primary-link" to="/workspace">开始演示</RouterLink>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.settings-stack { display: grid; gap: 20px; max-width: 1080px; margin: 0 auto; }
.settings-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; padding: 8px 0 6px; }
.section-kicker { color: var(--color-primary); font-size: 10px; font-weight: 800; letter-spacing: .08em; }
h2 { margin: 8px 0 10px; color: var(--color-text); font-size: clamp(26px, 4vw, 38px); line-height: 1.2; }
.settings-hero p { max-width: 700px; margin: 0; color: var(--color-text-secondary); line-height: 1.8; }
.back-link, .primary-link { display: inline-flex; align-items: center; justify-content: center; min-height: 40px; padding: 0 14px; border-radius: 9px; color: var(--color-primary); background: var(--color-primary-soft); font-size: 12px; font-weight: 700; text-decoration: none; white-space: nowrap; }
.status-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.status-card, .settings-card { display: grid; gap: 10px; padding: 20px; border: 1px solid var(--color-border); border-radius: 16px; background: #fff; box-shadow: var(--shadow-sm); }
.status-card__topline, .settings-card__heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.status-card__label, .count-label { color: var(--color-text-secondary); font-size: 11px; }
.status-card > strong { color: var(--color-text); font-size: 18px; }
.status-card > span, .status-card > small { color: var(--color-text-secondary); font-size: 11px; line-height: 1.6; }
.status-card > button { width: fit-content; margin-top: 2px; padding: 0; border: 0; color: var(--color-primary); background: transparent; cursor: pointer; font-size: 11px; font-weight: 700; }
.state-pill { display: inline-flex; align-items: center; gap: 6px; color: #b54708; font-size: 10px; font-weight: 700; }
.state-pill i { width: 7px; height: 7px; border-radius: 50%; background: #f79009; }
.state-pill--ready, .state-pill--online { color: #027a48; }
.state-pill--ready i, .state-pill--online i { background: #12b76a; }
.state-pill--offline { color: #b42318; }
.state-pill--offline i { background: #f04438; }
.settings-card h3 { margin: 5px 0 0; color: var(--color-text); font-size: 17px; }
.config-list { display: grid; gap: 0; }
.config-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 0; border-top: 1px solid #f0f2f5; color: var(--color-text-secondary); font-size: 12px; }
.config-row:first-child { border-top: 0; }
.config-row strong { color: var(--color-text); font-size: 12px; font-weight: 600; text-align: right; }
code { padding: 4px 7px; border-radius: 6px; color: #344054; background: #f2f4f7; font-size: 11px; }
.demo-list { display: grid; gap: 12px; margin: 2px 0 4px; padding: 0; list-style: none; }
.demo-list li { display: flex; align-items: center; gap: 12px; color: var(--color-text-secondary); font-size: 12px; line-height: 1.6; }
.demo-list b { display: grid; width: 26px; height: 26px; flex: 0 0 26px; place-items: center; border-radius: 8px; color: var(--color-primary); background: var(--color-primary-soft); font-size: 10px; }
.primary-link { width: fit-content; color: #fff; background: var(--color-primary); }
@media (max-width: 800px) { .status-grid { grid-template-columns: 1fr; } .settings-hero { align-items: flex-start; flex-direction: column; } }
@media (max-width: 560px) { .config-row { align-items: flex-start; flex-direction: column; gap: 6px; } .config-row strong { text-align: left; } }
</style>
