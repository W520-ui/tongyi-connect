# 第 2 阶段交付记录

本阶段已完成，停在 backend/phase-2，等待负责人“继续”后才进入第 3 阶段。有效说明为 D:\10178\Projects\tongyi-connect-frontend\docs\backend-prompt.md；实际改动仅位于主 worktree D:\10178\Projects\tongyi-connect。

## 1. 模块改动、分支与提交

起点 f59b5be，分支 backend/phase-2，由 backend/phase-1 派生。f59b5be 是进入第 2 阶段之前的独立语言回归修复：显式 reply_language 优先，缺失时跟随最新客户消息，不把语言关键词猜测写成指令；三句用户给定的西语均有回归。

本阶段的实现、测试与评测提交：

| 提交 | 内容 |
|---|---|
| 719c376 | 统一异步数据库、会话与工单状态、Agent 记忆和结构化分析，旧接口改由新表支撑 |
| 7de6a69 | 迁移原测试，覆盖并发、事务、版本、接管、上下文、分析、迁移和兼容回归 |
| 6bac824 | 30 条真实模型评测、临时数据库运行器、成功工具及事实评分、忽略生成结果 |

本文与 backend/README.md、PHASE_1.md 的更正作为单独文档提交；完整提交列表用 `git log --oneline f59b5be..backend/phase-2` 查看。没有推送或改写历史。

模块交付：

- **数据库与仓储：** SQLAlchemy 2.0 async、Alembic、aiosqlite；DATABASE_URL 默认锚定 backend/data/app.db；SQLite WAL、外键、busy_timeout。新增商家、会话、消息、运行、工单、商品和配送规则及辅助表，业务表带 merchant_id，只种 demo。迁移 0001 与 ORM 无差异；消息 seq 唯一且触发器禁止更新，工单有唯一未关闭约束，version 条件更新拒绝过期写入。旧会话/归档代码路径已删除，D5 不读取旧 workflow.db，种子脚本可重建新库。
- **会话与接管：** 唯一 handle_inbound 入口，按会话锁处理；成功消息组、effects、状态、工单及运行在一个事务保存。主模型失败保留客户消息与 error 运行、持久化失败计数，不生成助手历史或成功归档。pending_human 继续回答并去重；确认后 human_active 只保存普通客户消息和返回固定提示；解决后 resolved，下一条普通消息恢复 bot_active。reset 关闭旧会话、保留消息、新建 UUID，兼容旧 session_id 别名。
- **指令与语言：** 负责人已明确，human_active 期间仍执行本地指令，只暂停普通消息。所有斜杠指令及回复不进消息历史或咨询统计，未知指令也本地处理；/lang 校验三个枚举。¿、¡ 及补充西语词改善标注，回复语言指令继续遵守 f59b5be 的修复。
- **记忆与 Agent：** system_v2、实时商品和槽位、已有摘要、字符估算 token 预算；工具调用与全部结果成组保留或丢弃，工具结果有长度限制。可选后台摘要默认关闭，带版本条件保存并由 lifespan 管理。关注商品只来自成功工具副作用或已有状态，关键词和分析不会写入商品状态；报价可记住 quantity，仍保持单一美元价。错误运行保存已经观测到的工具轨迹、轮次、截断和 token 用量。
- **事后分析：** 默认启用，分析模型默认等于主模型；JSON Schema 优先，网关拒绝 response_format 时退回 JSON 提示，再校验；超时、关闭、坏结果时明确标注 heuristic。中文摘要要求包含外文咨询的中文译文；分析仅标注，不创建/取消工单或改变商品。主回复先保存，随后更新运行 outcome、来源、卡片和用量。
- **兼容与看板：** SQL 聚合新表，原 18 个工作流字段及旧请求字段不变。/dashboard/recent 实际新增 conversation_id，等于 session_id，id 是运行 ID；接管队列和确认接口使用工单 ID。队列保留触发运行的对客回复、分析后的中文摘要/标签和原始 issue_summary。PHASE_1.md 之前关于 conversation_id 的错误已更正；根 README 由 Claude 维护，后端对应 TODO 已撤销。
- **评测与文档：** evals/cases.json 有 30 条中英西语用例，涵盖报价、配送、追问、售后、数量和诱导承诺；提供真实模型 CLI 及可检查的通过率报告，全部使用临时库，不进 CI。README 和环境示例说明数据库、种子、D4、记忆、分析及当前 HTTP 边界。

依赖锁定为 SQLAlchemy 2.0.57、Alembic 1.20.1、aiosqlite 0.22.1，仅增加授权依赖及其传递依赖，没有模型 SDK 或 Agent 框架。

## 2. 测试与构建结果

环境：Windows、Python 3.12.11、uv 0.8.0、backend/.venv。后端命令在 backend 执行，前端命令在主 worktree 根目录执行。

```powershell
uv sync --frozen --extra dev
uv lock --check
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev ruff format --check .
$env:PYTHONIOENCODING = "utf-8"
uv run --frozen --extra dev pytest -q -o addopts='' --tb=short
uv run --frozen --extra dev pytest tests/test_demo_smoke.py -v
uv run --frozen --extra dev python -m app.scripts.eval_agent --list
npm ci
npm run build
npm run test --if-present
git diff --check
```

最终关键输出：

```text
uv sync: Audited 43 packages
uv lock --check: Resolved 44 packages
ruff check: All checks passed!
ruff format --check: 91 files already formatted
pytest: 176 passed, 1 warning in 63.58s (0:01:03)
four-step API demo: 1 passed, 1 warning in 0.74s
eval --list: 30 case IDs
npm ci: added 95 packages, audited 96 packages, found 0 vulnerabilities
npm run build: vue-tsc -b && vite build; 45 modules transformed; built in 238ms
npm run test --if-present: exit 0; no test script in this frontend, skipped
git diff --check: exit 0
```

没有 xfail，缺陷 1–12 全部通过。覆盖同会话并发两条咨询完整保留四条消息、跨实例过期写入拒绝和统计一致、统一事务回滚、只追加消息、工单去重/确认/解决/恢复、暂停语言与接管期间指令、幂等重放的内部服务逻辑、完整工具组和摘要版本、分析 Schema/JSON 回退/超时/坏字段、中文译文流程、种子重建及商家隔离。

唯一 warning 为现有 Starlette TestClient 对 httpx 的弃用提示；保持可见，未为消除它引入未授权的 httpx2。新前端 Vitest 未在本 worktree 运行，不能将旧前端 test 脚本跳过视为 Vitest 通过。

额外独立检查：

- **真实启动入口：** 用临时 DATABASE_URL、空模型密钥、随机本地端口启动 `uvicorn app.main:app --reload`。health/status/dashboard 均为 200，商品数 3，未配置模型的聊天为 503/LLM_NOT_CONFIGURED；Alembic 版本 0001、journal_mode=wal。检查并关闭自有 reload 进程树，端口不再监听，临时库清理完成。
- **离线 OpenAPI：** 通过脚本命令导出到临时目录，验证现有 8 个路径、原 18 个工作流字段、RecentInquiry.conversation_id、全部 $ref 可解析；没有新建数据库。新会话/工单/SSE 路由未提前引入。
- **文件范围：** 核对所有改动和新增文件均在授权路径；真实 backend/data 仍不存在。没有提交 .env、数据库、密钥或评测结果。未修改前端代码、前端 worktree、根 README 或其他归属文件。

核验脚本曾因常量名写错、SQLite 检查连接未显式关闭而失败；修正脚本后两个检查均 exit 0，残留临时文件已逐个清理。这些是核验脚本问题，未据此声称第一次检查通过。

## 3. 与说明的差异和限制

- 按负责人明确答复，斜杠指令先于 human_active 的普通消息暂停判断；这是对 5.4 顺序歧义的确认结果。相关行为已测试，不计历史或咨询数。
- 为 A.2 的客户消息统计和可恢复记录，模型运行失败仍保存 user 消息和 error 运行；成功归档继续仅包含 ok 运行。原测试的旧计数口径已改成新契约，保留不生成虚假回复/归档的断言。
- SQLite 按 D7 用于单机演示；version 已防止覆盖，但不同进程竞争可能返回 CONVERSATION_BUSY，不声称已实现多实例透明串行或数据库锁队列。
- 第 3 阶段的新 HTTP 接口、SSE、统一请求校验错误信封、商家鉴权占位尚未实现；内部已有的幂等与解决服务方法不代表对应 HTTP 接口已交付。
- 系统提示词和最新客户消息始终保留；如果两者本身已超出预算，全部历史省略。启用摘要仍不会修改历史消息。
- 真实模型手动演示和 30 条评测尚未执行。自动化验证了结构化译文流程，不能证明真实模型翻译质量；heuristic 摘要含原始外文，不声称它已经完成翻译。正则评测只提供基线，语义、否定句和译文还需要人工核对。

没有其他未报告的业务范围或接口形状变更。

## 4. TODO(owner) 和待决定事项

本阶段没有新增业务决策 TODO。继续保留既有 TODO(owner)：确认真实物流范围和配送时效，当前只有 ES 演示规则。报价不增加阶梯价、售后不承诺退款或自动批准。

根目录 README 已由用户指定交给 Claude，在前端分支统一处理；后端不维护此 TODO。human_active 的指令处理问题已经确认，无须再次提问。

## 5. 演示记录与手动验证

API 四步冒烟已通过：

1. 检索星云耳机、调用 ES 物流工具，返回 5–8 个工作日及英文回复。
2. 同会话追问沿用 headset-pro/ES，保留完整工具调用和结果。
3. 售后工具保存“耳机收到后无法开机”，工单显示问题、原因和回复，商家确认按工单 ID 执行。
4. 看板咨询 3、工单 1、待处理/失败 0、解决率 66.7%；核对最近归档的 conversation_id、确认标记和健康状态。

手动真实模型演示步骤见 backend/README.md 的“演示验证”：配置后端模型，运行主 worktree 的 npm run dev，依次执行商品配送、同会话追问、售后并确认、看板与状态检查。再发普通消息验证固定暂停提示，接管期间 /lang 和 /help 不增加咨询数；独立会话核对 AQ/Mars、三句西语、显式偏好和 reset 新 ID。

缺陷 12 输入“Hola, ¿cuánto tarda el envío de los auriculares a México?”，需要人工核对物流意图、需商家确认配送，以及中文摘要包含该咨询的中文译文。真实模型评测入口：

```powershell
uv run --frozen --extra dev python -m app.scripts.eval_agent
uv run --frozen --extra dev python -m app.scripts.eval_agent --case shipping-mx --case injected-price
```

结果默认写入忽略目录 evals/results/latest.json，含通过率、回复、摘要、来源和工具轨迹。运行前需可用模型密钥；脚本使用临时数据库，详细评分限制见 evals/README.md。

## 恢复入口

先核对 `git status --short --branch`、`git log --oneline -6`，确认 backend/phase-2 及本记录；不要重置未提交内容。查看本文和 backend/README.md 后继续。当前阶段已验收完成且未推送；等待负责人再次“继续”才能从本分支派生 backend/phase-3。
