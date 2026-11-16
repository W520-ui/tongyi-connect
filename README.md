# 通译智联

面向中小跨境商家的 AI 客服项目：海外客户在客户窗口咨询，Agent 用客户的语言回答商品、价格和物流问题；需要人工时转给商家，商家在控制台接管、查看中文摘要和数据看板。

**当前状态：** 后端已完成第 3 阶段（附录 A 的全部接口、SSE 流式回复、幂等、商家密钥）；新前端已接通这些真实接口，`src/fixtures/` 的演示数据已删除。真实模型的回复效果，要在后端配置模型密钥后验证（见下文）。

集成过程与验证记录见 [docs/INTEGRATION.md](docs/INTEGRATION.md)。

## 技术栈

- Vue 3、TypeScript、Vite、Vue Router、Pinia
- shadcn-vue（Reka UI + Tailwind CSS v4）、lucide、Inter 本地字体
- Vitest、Vue Test Utils、jsdom
- FastAPI、自研进程内 Agent、httpx
- SQLAlchemy 2.0 async、Alembic、aiosqlite，单机 SQLite 演示

## 本地运行

在仓库根目录执行。首次安装：

```powershell
cd backend
uv venv --python 3.12 --managed-python .venv
uv sync --frozen --extra dev
cd ..
npm ci
npm run dev
```

已经有 `backend/.venv` 时，只需 `uv sync --frozen --extra dev` 同步后端依赖。Python 需要 ≥ 3.11，虚拟环境保持在 `backend/.venv`。

`npm run dev` 同时启动 FastAPI（127.0.0.1:8000）和 Vite（127.0.0.1:5173），Vite 把 `/api` 转发给后端。打开 [客户窗口](http://127.0.0.1:5173/chat) 或 [商家控制台](http://127.0.0.1:5173/console/inbox)，Ctrl+C 停止两项服务。

- **模型密钥：** 在 `backend/.env` 配置 `AGENT_LLM_BASE_URL`、`AGENT_LLM_MODEL`、`AGENT_LLM_API_KEY`，详见 [backend/README.md](backend/README.md)。没有配置时，控制台、商品和状态页照常可用，客户发消息会提示“助手暂时不可用”。
- **商家密钥（可选）：** 后端配置了 `MERCHANT_API_KEY` 时，在控制台的“系统状态”页填写同一个密钥。密钥只保存在当前浏览器，不会写进前端代码。
- **数据库：** 默认是 `backend/data/app.db`，启动时自动迁移并写入种子数据。

## 页面

**客户窗口** `/chat`：界面支持中文、英文、西语，切换界面语言时同时设置会话的回复语言。回复逐字流式显示，查询商品或物流时显示进度，回复下方附商品卡片；可以转人工、开始新会话；刷新页面后恢复聊天记录。不显示意图、轨迹、商家摘要等内部信息。

**商家控制台** `/console/*`：

- `/console/inbox`：工单（待接管 / 处理中 / 已解决）与会话详情，包括中文摘要、对话记录、工具轨迹、确认接管、标记解决
- `/console/dashboard`：咨询量、自动解决率、意图与语言分布、最近咨询
- `/console/catalog`：商品资料
- `/console/system`：后端、模型、数据库状态，以及商家密钥

工单列表和看板每 10 秒刷新一次，浏览器标签页隐藏时暂停。

## 前端如何对接接口

接口契约见 [docs/backend-prompt.md](docs/backend-prompt.md) 附录 A。

- 会话 ID 存在 `sessionStorage`：打开页面先查询这个会话，不存在就新建。
- 发消息默认走 `POST /conversations/{id}/messages/stream`（SSE）。工具开始时丢弃同一轮已显示的开场白，30 秒收不到任何数据（包括心跳）就中止。
- 每条消息带一个 `client_message_id`。网络错误或超时后点“重试”，会复用同一个 ID，后端不会重复处理。
- 错误统一按附录 A.5 的错误码处理：客户窗口显示三语提示，控制台显示后端返回的中文说明。

```text
src/
├── api/          契约类型、请求封装与错误码、SSE 解析、各接口函数
├── components/   ui/（shadcn-vue）、chat/、console/
├── composables/  定时刷新（页面隐藏时暂停）
├── i18n/         客户窗口的三语文案与错误提示
├── layouts/      控制台布局
├── pages/        客户窗口与商家控制台
├── stores/       chat（客户窗口）、inbox、dashboard、catalog、system
├── test/         测试用的接口响应与假 fetch
├── theme/        控制台深色模式
└── utils/        时间、client_message_id 等工具
backend/          后端（第 0–3 阶段）、迁移、测试与评测
docs/             任务说明与接口契约、前端计划、设计截图、集成记录
```

单元测试放在被测代码旁边的 `__tests__/` 目录，文件名以 `.spec.ts` 结尾。

## 后端

后端运行器在 `agent/runtime.py`，以 httpx 直连 OpenAI 兼容服务。`ConversationService` 负责入站消息、会话锁与事务保存；仓储统一存储只追加的消息、运行、商品、配送规则和工单；`ContextBuilder` 按预算构建记忆；`PostAnalyzer` 生成结构化标注和中文摘要。附录 A.6 的旧接口在迁移期间保留。

完整配置、接管状态机、种子重建和 API 演示步骤见 [backend/README.md](backend/README.md)，各阶段记录见 `backend/PHASE_0.md` 至 `PHASE_3.md`。

## 验证

根目录执行：

```powershell
npm ci
npm run build
npm run test
```

backend 目录执行：

```powershell
uv sync --frozen --extra dev
uv lock --check
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev ruff format --check .
$env:PYTHONIOENCODING = "utf-8"
uv run --frozen --extra dev pytest
```

CI 会跑后端的 ruff 和 pytest，以及前端的 `npm ci`、`npm run build`、`npm run test`。
