# 通译智联 Web 端

通译智联是面向跨境服务场景的 Web 应用。当前版本已打通“海外客户咨询 → Agent 意图识别 → 商品资料检索 → 多语言回复 → 商家中文摘要 → 疑难问题人工接管 → 数据看板”的演示闭环。

## 技术栈

- Vue 3 + TypeScript
- Vite
- Vue Router
- Pinia
- 原生 Fetch 请求封装

## 本地运行

```bash
npm install
npm run dev
```

在项目根目录的 VS Code 终端执行 `npm run dev` 会同时启动 FastAPI 后端和 Vite 前端，
然后在浏览器打开 <http://127.0.0.1:5173/>。按 `Ctrl+C` 会停止两个开发服务。

`backend/.venv` 不存在时，请先按 [`backend/README.md`](backend/README.md) 创建后端虚拟环境并安装依赖。
如果只需要启动前端，可以执行 `npm run dev:frontend`；此时聊天和数据接口仍需要后端服务。

生产构建：

```bash
npm run build
```

## 目录约定

```text
src/
├── layouts/       应用级布局
├── router/        路由配置
├── services/      后端请求封装
├── stores/        Pinia 状态
└── views/         页面入口
```

复制 `.env.example` 为 `.env.local` 后，可通过 `VITE_API_BASE_URL` 配置后端 API 地址。开发服务器会将 `/api` 请求代理到本地 FastAPI（`http://127.0.0.1:8000`）。

## 后端

FastAPI 后端工程位于 [`backend/`](backend/README.md)，本地启动方式和配置说明见后端文档。API 健康检查入口为 `/api/v1/health`。

前端工作台已经接入 Agent 对话面板：浏览器请求本项目的 `/api/v1/agent/chat`，后端再以 `X-API-Key` 调用 AstrBot 的 `/api/v1/chat`。AstrBot 的 Key 只放在 `backend/.env`，不进入前端。

即使 AstrBot 尚未配置大模型提供商，默认的 `AGENT_LOCAL_FALLBACK_ENABLED=true` 也会使用本地演示策略完成商品检索、意图识别、双语话术和人工接管流程；配置模型后，AstrBot 的回复会自动替换本地话术。

看板与人机协同接口：

- `GET /api/v1/catalog/products`：商品知识库
- `GET /api/v1/dashboard/overview`：咨询量、意图和人工接管统计
- `GET /api/v1/dashboard/recent`：最近咨询归档
- `GET /api/v1/dashboard/handoffs`：待人工接管队列
- `POST /api/v1/dashboard/handoffs/{record_id}/acknowledge`：商家确认接管

## 演示流程

1. 打开工作台，发送“请用英文回复：星云降噪耳机 Pro 支持发往西班牙吗？”，查看语言识别、询价与物流意图、商品命中和英文回复。
2. 在同一会话继续发送“那它的物流要多久？”，Agent 会从上一轮归档中恢复商品上下文。
3. 发送“客户说耳机收到后无法开机，帮我登记售后”，查看人工接管队列，点击“确认接管”完成闭环。
4. 查看意图统计、语言分布和最近咨询归档；设置页可以检查后端健康状态与现场演示顺序。

前端请求的 Agent 超时为 70 秒，后端连接 AstrBot 的建立连接超时为 5 秒。这样模型有足够的生成时间，AstrBot 未启动时也能快速进入本地演示策略。
