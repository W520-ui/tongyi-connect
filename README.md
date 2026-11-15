# 通译智联 Web 端

通译智联是面向跨境服务场景的 Web 应用。当前版本已打通“海外客户咨询 → Agent 意图识别 → 商品资料检索 → 多语言回复 → 商家中文摘要 → 疑难问题人工接管 → 数据看板”的演示闭环。

## 技术栈

- Vue 3 + TypeScript
- Vite
- Vue Router
- Pinia
- shadcn-vue（Reka UI + Tailwind CSS v4）+ lucide 图标 + Inter 字体
- Vitest + Vue Test Utils（前端单元测试）
- 后端：FastAPI + 自研进程内 Agent 运行时（Python 3.11+）

## 本地运行

```bash
npm install
npm run dev
```

在项目根目录的 VS Code 终端执行 `npm run dev` 会同时启动 FastAPI 后端和 Vite 前端，
然后在浏览器打开 <http://127.0.0.1:5173/>。按 `Ctrl+C` 会停止两个开发服务。Agent 运行在后端进程内，不需要再启动任何外部 Agent 服务。

`backend/.venv` 不存在时，请先按 [`backend/README.md`](backend/README.md) 创建后端虚拟环境并安装依赖。
如果只需要启动前端，可以执行 `npm run dev:frontend`；此时聊天和数据接口仍需要后端服务。

生产构建：

```bash
npm run build
```

前端单元测试（运行在 jsdom 中，不需要启动后端）：

```bash
npm run test
```

## 目录约定

前端分成两个互相独立的页面：

- 客户窗口 `/chat`：面向海外客户的聊天页，界面支持中文、英文、西班牙语；
- 商家控制台 `/console`：收件箱、数据看板、商品资料、系统状态，支持深色模式。

```text
src/
├── api/           接口契约类型（docs/backend-prompt.md 附录 A）
├── components/    ui/（shadcn-vue 组件）、chat/（客户窗口）、console/（商家控制台）
├── fixtures/      视觉原型阶段的演示数据（接上模拟后端后删除）
├── i18n/          客户窗口的三语文案
├── layouts/       控制台布局
├── pages/         页面入口
├── router/        路由配置
├── stores/        Pinia 状态
├── lib/           工具函数（cn）
├── style.css      Tailwind 入口与主题变量（浅色 / 深色）
└── theme/         控制台深色模式开关
```

单元测试放在被测代码旁边的 `__tests__/` 目录里，文件名以 `.spec.ts` 结尾。前端重写的计划和进度见 [`docs/frontend-plan.md`](docs/frontend-plan.md)。

复制 `.env.example` 为 `.env.local` 后，可通过 `VITE_API_BASE_URL` 配置后端 API 地址。开发服务器会将 `/api` 请求代理到本地 FastAPI（`http://127.0.0.1:8000`）。

## 后端

FastAPI 后端工程位于 [`backend/`](backend/README.md)，本地启动方式和配置说明见后端文档。API 健康检查入口为 `/api/v1/health`。

前端工作台请求 `POST /api/v1/agent/chat`，由后端进程内的自研 Agent 运行时处理：会话管理、指令响应、工具调用（商品检索 / 报价 / 物流 / 参数 / 售后登记）和 OpenAI 兼容模型调用都在服务端完成，浏览器不接触任何模型密钥。

Agent 依赖可用的对话模型。未配置 `AGENT_LLM_API_KEY`、无法连接模型服务或工具调用超过轮次上限时，`/api/v1/agent/chat` 返回 502/503 错误，由前端展示错误提示。

看板与人机协同接口：

- `GET /api/v1/catalog/products`：商品知识库
- `GET /api/v1/dashboard/overview`：咨询量、意图和人工接管统计
- `GET /api/v1/dashboard/recent`：最近咨询归档
- `GET /api/v1/dashboard/handoffs`：待人工接管队列
- `POST /api/v1/dashboard/handoffs/{record_id}/acknowledge`：商家确认接管

## 自研 Agent 运行时

`backend/app/agent/` 与 FastAPI 同进程，不额外占用端口：

- `engine.py`：编排核心，指令优先 → 会话加载 → 业务分析 → LLM function calling 循环 → 归档
- `session.py`：SQLite 多轮会话与商品上下文（`/reset` 可清空）
- `registry.py` + `tools/`：工具注册与 JSON Schema 导出，新增工具只需 `@tool(...)`
- `providers/`：`LLMProvider` 协议 + OpenAI 兼容实现（httpx 直连，不装 SDK）
- `commands.py`：`/help /reset /lang /product /handoff`

原 `services/workflow.py` 继续负责语言与意图识别、商品匹配、商家中文摘要和看板归档。

## 演示流程

1. 打开工作台，发送“请用英文回复：星云降噪耳机 Pro 支持发往西班牙吗？”，查看语言识别、询价与物流意图、商品命中和英文回复。
2. 在同一会话继续发送“那它的物流要多久？”，Agent 会从会话上下文恢复上一轮命中的商品。
3. 发送“客户说耳机收到后无法开机，帮我登记售后”，查看人工接管队列，点击“确认接管”完成闭环。
4. 查看意图统计、语言分布和最近咨询归档；设置页可以检查后端健康状态与现场演示顺序。

前端请求的 Agent 超时为 70 秒；模型连接建立超时 5 秒、生成超时由 `AGENT_LLM_TIMEOUT_SECONDS` 控制（默认 60 秒）。
