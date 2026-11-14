# 通译智联后端

基于 FastAPI 的后端服务。当前提供版本化 API、AstrBot Agent 适配层、跨境服务工作流、商品知识库和演示看板统计。

## 环境要求

- Python 3.11 或更新版本

## 本地运行

在 `backend/` 目录下执行：

```bash
python -m venv .venv
```

Windows PowerShell 激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

安装项目依赖并启动开发服务：

```bash
python -m pip install -e .
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

服务默认运行在 `http://127.0.0.1:8000`。开发模式下可在 `/docs` 查看 API 文档，健康检查地址为 `/api/v1/health`。

## AstrBot 接入

AstrBot 官方 HTTP API 文档：

- [AstrBot HTTP API](https://docs.astrbot.app/dev/openapi.html)
- [API Scope 与接口对照](https://docs.astrbot.app/dev/openapi-scopes.html)
- [Agent 执行方式](https://docs.astrbot.app/use/agent-runner.html)

本项目的适配器调用 AstrBot 的 `POST /api/v1/chat`，使用 `X-API-Key` 请求头和 `chat` scope。AstrBot 默认地址是 `http://127.0.0.1:6185`，在 `.env` 中配置：

```dotenv
ASTRBOT_BASE_URL=http://127.0.0.1:6185
ASTRBOT_API_KEY=你的AstrBot_API_Key
ASTRBOT_TIMEOUT_SECONDS=60
AGENT_LOCAL_FALLBACK_ENABLED=true
```

`AGENT_LOCAL_FALLBACK_ENABLED` 默认开启。AstrBot 返回“没有可用模型”或暂时不可用时，后端会继续用本地规则策略完成演示；生产环境可将其设置为 `false`，让配置问题直接暴露。

项目对外接口为 `POST /api/v1/agent/chat`，请求示例：

```json
{
  "message": "请用英文回复：这款产品支持发往西班牙吗？",
  "session_id": "demo-session-001",
  "username": "demo-user"
}
```

AstrBot API Key 只保存在后端环境变量中，浏览器不会直接接触 AstrBot 服务凭证。适配器请求 AstrBot 的 SSE WebChat 接口，并在服务端聚合为统一 JSON 响应。

工作流接口：

- `GET /api/v1/catalog/products`：商品知识库
- `GET /api/v1/dashboard/overview`：咨询量、意图和人工接管统计
- `GET /api/v1/dashboard/recent`：最近咨询归档
- `GET /api/v1/dashboard/handoffs`：待人工接管队列
- `POST /api/v1/dashboard/handoffs/{record_id}/acknowledge`：商家确认接管

演示会话按 `session_id` 记忆最近命中的商品，方便客户用“它的物流呢？”等追问继续咨询。咨询摘要、商品上下文和接管状态存储于 `backend/data/workflow.db`，服务重启后保留。

## 配置

复制 `.env.example` 为 `.env`，按需调整应用名称、调试模式、日志级别、API 前缀和前端跨域来源。敏感配置不要提交到版本库。

`AGENT_LOCAL_FALLBACK_ENABLED=true` 时，即使 AstrBot 没有可用模型，接口仍会完成意图识别、商品检索、双语话术、商家摘要和人工接管归档。AstrBot 连接建立超时为 5 秒，避免演示等待过久；模型生成仍使用完整的超时时间。

## 目录结构

```text
backend/
├── app/
│   ├── api/           API 路由及版本入口
│   ├── core/          配置与应用基础设施
│   ├── models/        持久化模型预留
│   ├── repositories/  数据访问层预留
│   ├── schemas/       请求和响应模型
│   ├── services/      业务服务层预留
│   └── main.py        FastAPI 应用入口
├── .env.example
└── pyproject.toml
```
