# 通译智联

面向中小跨境商家的 AI 客服项目。本地集成分支 `codex/front-back-integration` 已合并 `frontend/v2` 的新界面和 `backend/phase-2` 的后端。

**当前状态：** 新前端完成视觉原型，客户聊天、收件箱、看板和系统页仍使用 `src/fixtures/` 的演示数据。页面中的回复、接管操作和指标尚未调用真实后端。后端第 2 阶段已完成数据库、会话与工单状态、记忆和事后分析；新会话/工单接口和 SSE 在第 3 阶段交付后，再接通新前端。

本次合并记录、验证结果和恢复入口见 [docs/INTEGRATION.md](docs/INTEGRATION.md)。

## 技术栈

- Vue 3、TypeScript、Vite、Vue Router、Pinia
- shadcn-vue（Reka UI + Tailwind CSS v4）、lucide、Inter 本地字体
- Vitest、Vue Test Utils、jsdom
- FastAPI、自研进程内 Agent、httpx
- SQLAlchemy 2.0 async、Alembic、aiosqlite，单机 SQLite 演示

## 本地运行

请在 `D:\10178\Projects\tongyi-connect` 主目录执行；原 `tongyi-connect-frontend` worktree 和两个阶段分支仍保留。

首次安装后端环境：

```powershell
cd D:\10178\Projects\tongyi-connect\backend
uv venv --python 3.12 --managed-python .venv
uv sync --frozen --extra dev
cd ..
npm ci
npm run dev
```

已经有 backend/.venv 时，只需 `uv sync --frozen --extra dev` 同步后端依赖。Python 需要 ≥ 3.11，虚拟环境保持在 backend/.venv。

`npm run dev` 同时启动 FastAPI 和 Vite；打开 [客户窗口](http://127.0.0.1:5173/chat) 或 [商家控制台](http://127.0.0.1:5173/console/inbox)。Vite 固定监听 127.0.0.1，端口被占用时以终端显示的地址为准。Ctrl+C 停止两项服务。只查看视觉原型可以执行 `npm run dev:frontend`，无需模型密钥。

后端密钥、模型与数据库配置见 [backend/README.md](backend/README.md)。默认数据库为 backend/data/app.db，启动时运行迁移并初始化种子。当前 UI 使用样例数据，配置模型密钥不会使新界面自动连接后端。

## 页面与目录

客户窗口 `/chat` 支持中文、英文、西语界面，展示消息、商品卡片与转人工状态。商家控制台包含：

- `/console/inbox`：工单列表与会话详情
- `/console/dashboard`：咨询、意图、语言和最近咨询
- `/console/catalog`：商品资料
- `/console/system`：系统状态展示

```text
src/
├── api/          附录 A 的契约类型；请求封装与 SSE 客户端待实现
├── components/   ui/、chat/、console/
├── fixtures/     当前视觉原型的演示数据
├── i18n/         客户界面的三语文案
├── layouts/      控制台布局
├── pages/        客户窗口与商家控制台
├── stores/       当前本地演示状态
├── theme/        浅色与深色主题
└── utils/        时间等工具及单元测试
backend/          已完成第 2 阶段的后端、迁移、测试与评测
docs/             任务说明、前端计划、设计截图与集成记录
```

[docs/backend-prompt.md](docs/backend-prompt.md) 是有效的后端任务与接口契约；[docs/frontend-plan.md](docs/frontend-plan.md) 记录前端后续阶段。设计截图在 docs/design/。

## 已交付后端

健康与状态接口为 `GET /api/v1/health` 和 `GET /api/v1/status`。现有聊天、商品、看板及确认接管接口继续保留，新前端尚未使用它们。

后端运行器在 agent/runtime.py，以 httpx 直连 OpenAI 兼容服务。ConversationService 负责入站消息、会话锁与事务保存；仓储统一存储只追加消息、运行、商品、配送和工单；ContextBuilder 按预算构建记忆；PostAnalyzer 生成结构化标注及中文摘要。未配置模型时，普通聊天返回 LLM_NOT_CONFIGURED，本地指令和商品/状态接口仍可使用。

完整配置、接管状态机、种子重建及 API 四步演示验证见 [backend/README.md](backend/README.md)。阶段记录见 backend/PHASE_0.md、PHASE_1.md、PHASE_2.md。

## 验证

主目录执行：

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

本地 CI 保留后端 ruff/pytest，以及前端 npm ci/build/test --if-present；合并后 test 脚本会实际运行 Vitest。具体结果及尚未完成的真实接口联调见集成记录。
