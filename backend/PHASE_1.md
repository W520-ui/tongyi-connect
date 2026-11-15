# 第 1 阶段交付记录：边界与工具调用

## 起点与恢复

- 有效说明：`D:\10178\Projects\tongyi-connect-frontend\docs\backend-prompt.md`，已完整阅读；旧版仓库说明不作为执行依据。
- 工作仓库：`D:\10178\Projects\tongyi-connect`；分支 `backend/phase-1`，从第 0 阶段交付 `17b9b1a` 创建。
- 用户已回复“继续”，并追加两项验收：Mars 必须明确为参数校验失败；前端 CI 在 build 后执行 `npm run test --if-present`。
- 当前状态：第 1 阶段已完成。停在本阶段，等待负责人再次回复“继续”后才进入第 2 阶段。
- Python 3.12.11、uv 0.8.0；虚拟环境仍是 `backend/.venv`。
- 恢复前核对 `git status --short --branch`、`git log -6 --oneline` 和本记录；不重置工作区、不改写提交、不推送、不触碰前端 worktree。
- 全部后端与测试、两份 README、背景架构评审和旧前端 src/services 的初始阅读记录见 PHASE_0.md；本阶段再次核对有效说明及最终代码。

## 1. 模块改动与提交

- **领域与商品：** 三个商品逐字段从原 PRODUCTS 提取到 app/seed/catalog.json，离线比较与第 0 阶段完全相同。CatalogService 当前使用内存种子；配送规则只包含三条 ES，保留原时效。ISO 国家校验包含 249 个已分配代码。
- **护栏与会话：** 单张关键词规则表，拉丁词边界和明确词形，语言要求按短语识别。显式 reply_language 与检测语言独立保存；匿名请求返回独立 UUID session_id；本地 asyncio 会话锁保留 FIFO 处理并可通过协议替换。斜杠指令不进入模型历史、不计入咨询量；reset 清空商品和槽位，不从归档回退恢复。
- **工具与运行器：** 五个 Pydantic 工具、ToolOutput 与类型化 effects，移除无数据源的 knowledge_search。异步事件运行器不写数据库；每轮完整 schema、最后一轮 tool_choice=none；坏 JSON/参数、未知工具、工具异常/超时回传失败结果。同轮 gather 并发，完成事件和 steps 反映实际顺序；处理流式 index 片段、总时限、取消清理、长度截断和 token 累计。
- **模型与资源：** 唯一 Settings，backend 锚定 .env；SecretStr、共享 httpx.AsyncClient、可配置温度/输出上限、最多两次重试与 Retry-After。单调用与总时限有不同错误码，连接超时重试耗尽仍为 LLM_TIMEOUT。上游诊断写日志并遮蔽密钥，对浏览器返回中文通用消息。全部业务资源在 lifespan 创建和关闭，删除缓存引擎与进程内 metrics 单例。
- **仓储与服务：** 旧 SQLite 会话/归档访问移到 repositories；添加原因、issue_summary、槽位、指令和工单创建标记及完整轨迹，持久化失败计数。AnalyticsService 用 SQL 实时聚合，同一读事务形成看板快照。ConversationService.handle_inbound 统一处理消息和应用 effects；坏旧历史 JSON 保持可恢复。
- **HTTP 与提前交付：** HTTP 模型统一放在 api/v1/schemas，卡片在 presenters。旧请求字段、成功信封和工作流原有 18 字段不变，增加 session_id/trace。交付 GET /api/v1/status 与离线 OpenAPI 导出。更正：第 1 阶段并未给最近归档增加 conversation_id；先前记录有误，第 2 阶段按附录 A.6 补齐。
- **工程与测试：** .gitignore 清理 AstrBot 残留，忽略生成的 backend/openapi.json；打包包含种子与提示词，无新增依赖。保留并迁移原测试验证意图，缺陷 1–11 去掉 xfail，仅缺陷 12 保留。增加运行器、重试、生命周期、无资源构造导入、AST 依赖合约及导出测试。
- **用户追加项：** Mars 回归同时检查传给模型的工具结果 ok=false、TOOL_VALIDATION_ERROR、非空错误消息以及 HTTP trace 失败状态；unconfirmed 结果不能通过。CI 前端 build 后增加可选 test，旧前端无脚本时跳过。

提交依次为：

| 提交 | 内容 |
|---|---|
| `9ab2984` | `test: require Mars validation errors and run optional frontend tests` |
| `edf5b30` | `refactor(backend): isolate services and make tool effects explicit` |
| `7e5bf2c` | `test(backend): cover runner failures, model retries and resource boundaries` |
| 本文件所在的交付提交 | `docs(backend): document phase 1 behavior, validation and recovery` |

没有推送、合并或改写历史；只改 backend/**、.github/workflows/** 和根 .gitignore。前端 worktree 与 frontend 分支没有修改或切换。

## 2. 测试与构建证据

后端命令均在 `D:\10178\Projects\tongyi-connect\backend` 执行：

| 命令 | 关键输出 |
|---|---|
| `uv sync --frozen --extra dev` | Audited 37 packages，退出码 0 |
| `uv lock --check` | Resolved 38 packages，退出码 0 |
| `uv run --frozen --extra dev ruff check .` | All checks passed! |
| `uv run --frozen --extra dev ruff format --check .` | 71 files already formatted |
| `uv run --frozen --extra dev pytest -q -o addopts='' --tb=short` | **124 passed, 1 xfailed, 1 warning in 32.92s** |
| `uv run --frozen --extra dev pytest tests/test_demo_smoke.py -v` | test_readme_demo_four_steps PASSED；1 passed in 0.59s |
| `uv run --frozen --extra dev python -m app.scripts.export_openapi` | 输出 backend/openapi.json，退出码 0 |

Windows 测试输出前设置 `$env:PYTHONIOENCODING = 'utf-8'`。唯一预期失败是第 2 阶段缺陷 12，strict 且限定 AssertionError。唯一警告是锁定的 Starlette TestClient 对 httpx 适配的现有弃用提示；没有隐藏或为此增加未授权依赖。

前端命令在后端所在主 worktree 根目录执行：

| 命令 | 关键输出 |
|---|---|
| `npm ci` | added 95 packages；found 0 vulnerabilities |
| `npm run build` | vue-tsc -b 与 Vite 成功；45 modules transformed；built in 186ms |
| `npm run test --if-present` | 退出码 0，无 test 脚本，正常跳过 |

本分支仍是旧前端；可选 test 的跳过不代表新前端 Vitest 已验证。CI 已配置，本机同等命令通过；遵守不推送要求，没有声称远程 GitHub Actions 已运行。

额外离线和启动验证：

- 通过标准库解析 OpenAPI：8 条路径完整，全部本地 $ref 可解析；旧请求字段不变，工作流仅增加 session_id 和 trace。
- 用 AST 从 `17b9b1a` 提取 PRODUCTS，与 catalog.json 逐字段相等；三条规则均为 ES，days_text 与原 shipping_days 一致；ISO 集合为 249 项。
- 真正运行 `python -m uvicorn app.main:app --reload`，仅监听本机随机端口，数据库放系统临时目录、覆盖为空模型密钥。health/status/catalog 成功；聊天返回 503 与 LLM_NOT_CONFIGURED。finally 终止自有 reloader 进程树，临时目录自动清理。
- 全模块导入测试阻止 Settings、SQLite 与 AsyncClient 构造，仍能导入所有模块；离线导出同样不启动业务资源。
- `git diff --check` 通过，授权文件范围核对通过；真实 backend/data 目录仍不存在，生成 OpenAPI 已忽略，没有提交真实 .env、数据库或密钥。

## 3. 与说明的差异和阶段边界

没有第 1 阶段范围、旧接口形状、依赖或文件归属方面的偏离。AST 导入扫描测试作为说明允许的 import-linter 替代，随 pytest 进入 CI。

第 1 阶段按要求继续使用旧表。会话保存和归档仍为两个提交，只保证同进程同会话串行；SQLAlchemy、append-only 消息、新表统一事务、版本锁和 D4 完整状态机属于第 2 阶段。当前 reset 清空旧 session；关闭旧会话并返回新 ID 留待新模型。当前上下文按条数成组裁剪，完整 token 预算和摘要也留到第 2 阶段。

结构化事后分析与中文译文未实现，缺陷 12 保留预期失败。确认接管后暂停机器人、新会话/工单 API、幂等与 SSE 均未提前宣称交付。现有 flags.enable_streaming 可使用内部流式模型读取，但旧接口仍返回普通 JSON。

真实模型手动验证未执行；按验收要求交付自动化假模型结果与完整手动步骤。根 README 的旧模块说明按文件归属保持原样，交由负责人协调。

## 4. TODO(owner) 与待决定问题

- **D2 已有事项，现写入种子规则：** 确认真实可配送范围；当前仅 ES 为已知演示规则，不扩展国家、不增加价格或退款政策。
- **已撤销的协调事项：** 用户明确指定根 README 由 Claude 在前端分支统一更新，后端不再维护此 TODO。
- 本阶段没有其他新增业务选择或需立即阻塞的问题。

## 5. 演示记录与手动步骤

四步 API 自动化使用脚本化模型并通过：

1. 第一条英文回复要求与西班牙咨询：catalog_search 后 catalog_shipping(ES)，返回耳机的 5–8 个工作日和英文回复。
2. 同会话追问：恢复 headset-pro/ES，再次成功查询物流；真实工具结果驱动卡片与商品置信度。
3. 售后：after_sales_record 保存“耳机收到后无法开机”，队列出现一条记录；确认接口成功，待处理变为 0。
4. 看板与历史：咨询 3、接管 1、待处理 0、失败 0、解决率 66.7%；英文 1/中文 2，物流 2/售后 1；最近归档与确认标记一致，历史保留 6 条问答及实际工具消息，健康检查通过。

缺陷 11 单独验证 ES 成功、AQ unconfirmed、Mars 参数校验失败并送回模型；Mars 的错误标记、错误码、说明及失败轨迹均为必须通过的断言。

真实模型手动验证（未执行）：

1. 后端 .env 配置可用模型地址、名称和密钥；主 worktree 根目录执行 npm ci、npm run dev，打开 http://127.0.0.1:5173/。记录看板基线，发送“请用英文回复：星云降噪耳机 Pro 支持发往西班牙吗？”，核对英文、耳机和 5–8 个工作日物流；查看响应中成功的工具轨迹。
2. 发送“那它的物流要多久？”，核对沿用 headset-pro 与 ES，无商品或时效漂移。
3. 发送“客户说耳机收到后无法开机，帮我登记售后”，检查原因/issue_summary，点击确认接管，核对待处理队列减少和归档标记。
4. 看板咨询比基线增加 3、人工接管增加 1，检查语言/意图分布与最近三条记录；设置页健康正常，访问 /api/v1/status 核对模型与数据库状态。

再用独立会话询问南极洲与 Mars，分别核对需商家确认和参数校验失败；/lang es-ES 后发两条英文消息核对偏好持久化，reset 后核对商品清空。旧页面未展示 trace 时，从浏览器网络面板查看聊天响应。完整配置、命令与阶段限制见 backend/README.md。

## 第 2 阶段恢复入口

负责人再次回复“继续”后，先核对本记录、Git 状态和第 1 阶段提交，然后从 backend/phase-1 创建 backend/phase-2。重新以有效 backend-prompt.md 的第 2 阶段为准：授权依赖与迁移、新数据模型/种子脚本、统一事务和乐观锁、D4 接管状态机、完整 ContextBuilder、D3 事后分析、旧接口适配与离线评测。第 2 阶段需让缺陷 12 通过，保持旧接口及演示；不要提前进入第 3 阶段。
