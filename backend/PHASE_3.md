# 第 3 阶段：新接口

从 codex/front-back-integration（fc70e59）创建并完成 backend/phase-3。本阶段按 docs/backend-prompt.md 附录 A 实现；新前端仍归 Claude 负责，等待前端接入后再联调。本报告只落在允许修改的 backend/** 范围。

## 改动

- 新增会话创建、查询、回复语言更新、历史分页、消息发送与 SSE、重置和主动转人工接口；工单列表、确认、解决接口；响应 HTTP 模型集中在 app/api/v1/schemas/。
- 历史按消息序号倒序分页查询、正序返回，隐藏工具消息及本地指令，恢复助手工作流卡片。
- 新接口只接受已有会话 ID；消息正文先 trim 再校验长度。client_message_id 对普通消息、暂停消息、斜杠指令及已失败消息都幂等。指令回执写入新增 Alembic 0002，不污染消息历史和统计。
- SSE 的运行任务由应用后台任务管理器持有，订阅队列和推送连接分开。预检错误返回 JSON；运行开始后的错误以 error 事件结束；正常流程先发 completed，再发 analysis，每 15 秒发 : ping。客户端断开不取消处理或落库。
- 新商家路由校验 X-Merchant-Key；仅在 MERCHANT_API_KEY 有非空值时启用。未配置时启动日志告警；日志遮蔽模型和商家密钥。
- 统一 FastAPI 请求校验、业务及意外服务端错误为 A.5 信封，同时保留顶层 detail 和原有兼容路由。OpenAPI 包含附录接口与 SSE 命名事件 schema。
- backend/.env.example 增加留空的 MERCHANT_API_KEY。现有根 .gitignore 已忽略 backend/openapi.json，无需改动。

## 阶段边界

仅修改 backend/**。没有改动 src/**、根目录配置、根 README.md、scripts/**、.github/workflows/** 或根 .gitignore；没有推送或改写已有历史。human_active 期间本地斜杠指令仍按此前确认正常执行，普通消息只保存客户内容并返回暂停提示。

接口契约有一处迁移兼容交集：A.2 的 RecentInquiry 没列 issue_summary，A.6 又要求同一路径旧响应保持形状。GET /dashboard/recent 保留既有 issue_summary 字段并继续提供 conversation_id；前端可忽略多出的字段。其余旧接口形状和确认接管行为保留。

## 验证

- uv lock --check：通过。
- uv run --frozen --extra dev ruff check .：通过。
- uv run --frozen --extra dev ruff format --check .：103 个文件均已格式化。
- uv run --frozen --extra dev pytest -q：239 passed；测试只使用临时数据库与假模型。
- uv run --frozen --extra dev python -m app.scripts.export_openapi --output "$env:TEMP/tongyi-openapi-phase3.json"：通过。结构化检查到 17 条 API 路径，SSE 文档列出 tool_started、tool_finished、delta、completed、analysis、error。
- 使用 curl.exe -N 对脚本化模型实测 SSE：依次收到 delta、completed、analysis，之后停止演示服务。真实模型质量未在本阶段验证。
- npm ci：通过，安装 198 个包；npm 报告 5 个 moderate 级依赖告警。
- npm run build：通过，Vite 转换 2860 个模块。
- npm run test：3 个文件、11 项通过。前端工作区只用于验证，没有修改。

## 演示

自动化命令：uv run --frozen --extra dev pytest tests/test_phase3_api.py::test_phase3_demo_smoke_uses_new_conversation_and_merchant_apis -v。脚本化模型通过新接口依次验证会话创建、商品与 ES 物流查询、同会话追问、售后工单、商家确认接管、human_active 暂停消息、会话历史、看板和工单队列。四条客户消息计入咨询数，三次机器人回复记入运行，人工暂停不调用模型。

真实模型演示仍需后端 .env 配置模型地址、名称和密钥；Claude 接通新前端后再共同完成 A.7 的四步检查，并验证真实模型回复与中文商家摘要。自动化和本次 curl 使用假模型，不能代表真实模型效果。

## 前端接入事项

- 会话启动时读取 sessionStorage 中的 conversation_id，先 GET 会话；收到 CONVERSATION_NOT_FOUND 后 POST 新会话，再保存返回的 id。历史使用 GET /conversations/{id}/messages，需要更多内容时以最早一条 seq 请求 before_seq。
- 每次客户消息生成并保留一个符合 [A-Za-z0-9_-]{1,64} 的 client_message_id；重试、超时恢复时复用原 ID。消息内容 trim 后为 1–20000 字符。
- 默认使用 POST /conversations/{id}/messages/stream，发送 Accept: text/event-stream。解析具名 SSE 事件；completed.data.reply 是最终回复，analysis 更新卡片。工具轮开始时清除同轮已显示的临时 delta；超时或网络失败后可以重新加载历史。error 事件结束当前流，: ping 是注释心跳，不是业务事件。
- 看板和工单轮询分别调用 GET /dashboard/overview、GET /dashboard/recent、GET /handoffs；工单动作调用 /handoffs/{id}/acknowledge 与 /resolve。当部署配置 MERCHANT_API_KEY 后，上述商家请求都要带 X-Merchant-Key。在前端支持该头之前保持后端密钥未配置，否则商家请求会返回 401。
- 商品、健康和系统状态使用 GET /catalog/products、GET /health、GET /status；更新语言、重置及主动转人工使用对应会话 PATCH/POST 路由。工作流结果公开字段没有旧兼容字段 session_id，请统一读 conversation_id。

## 问题与待确认

- 本阶段没有新增 TODO(owner)。原 D2 物流真实覆盖范围仍待负责人确认；种子只确认西班牙（ES）。
- /dashboard/recent 的旧 issue_summary 兼容字段已在上文记录，需 Claude 的类型和响应解析允许忽略额外字段。
- 前端添加 X-Merchant-Key 请求头的代码完成并部署配置后，再设置真正的 MERCHANT_API_KEY；不要把密钥写入前端源码。

## 提交

分支：backend/phase-3。

- fcb1a59 feat(api): add contract routes and streaming
- ade7fbf test(api): cover phase 3 contract and streaming

阶段到此结束；等待 Claude 接好前端，再按附录 A 一起联调。
