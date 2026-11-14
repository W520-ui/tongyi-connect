# 前端开发计划（Claude 负责）

- **分工：** 后端由 GPT6.1solmax 按 [`refactor-prompt.md`](refactor-prompt.md) 执行；前端由 Claude 按本文件执行。两边只通过接口契约 `docs/api-contract.md`（前端起草、负责人确认）对接。
- **依据：** [`architecture-review.md`](architecture-review.md) 里的前端问题（B6、B7，以及 2.5 的前端部分）和目标架构 3.6。

## 1. 文件归属

| 谁 | 负责的文件 |
|---|---|
| 前端（Claude） | `src/**`、`public/**`、`index.html`、`package.json`、`package-lock.json`、`vite.config.ts`、`tsconfig*.json`、`scripts/dev-all.mjs`、根目录 `README.md`、`docs/frontend-plan.md`、`docs/api-contract.md` |
| 后端（GPT6.1solmax） | `backend/**`、`.github/workflows/**`、根目录 `.gitignore` |
| 负责人（你） | 确认决策和接口契约；合并分支；通知后端删除兼容层 |

两边都不改对方的文件；确实需要改时，先告诉负责人。

## 2. 工作方式

- 在独立的 git worktree 和 `frontend/*` 分支上开发，不碰后端的工作目录和分支。
- 每个阶段一个 PR（或一组提交），由你合并；不推送，也不直接改 `main`。
- 复用现有的 `request()` 封装、CSS 变量和视觉风格，不引入 UI 组件库；界面文案保持简体中文。
- 每个阶段都要验证：`vue-tsc -b` 和 `vite build` 通过；单元测试通过；在内置浏览器里按演示脚本走一遍，并截图记录。

## 3. 需要你确认的前端决策

- **F-D1 新依赖：** `markdown-it`（渲染回复，设置 `html: false`，防止注入）；开发依赖 `vitest`、`@vue/test-utils`、`jsdom`（测试），以及 `openapi-typescript`（从后端导出的 OpenAPI 生成类型）。（建议：允许。）
- **F-D2 刷新后恢复会话：** F1 阶段先把会话 ID 和消息列表存在浏览器的 `sessionStorage` 里（关掉标签页就清空）；后端的历史接口上线后，改为以服务端为准。（建议：同意。）
- **F-D3 操作按钮：** 在聊天区提供"新会话""转人工""回复语言"三个控件；输入框里的 `/reset` 等斜杠指令继续保留，作为开发时的快捷方式。（建议：同意。）

## 4. 分阶段计划

### F0 准备（现在就能做）

1. 起草 `docs/api-contract.md`：后端第 3 阶段新接口的请求和响应 JSON、SSE 事件格式、统一错误信封和错误码，以及 `/status`。交你确认后，后端照此实现。
2. 搭测试基建：`vitest` + `@vue/test-utils`，新增 `npm run test`。

**验收：** 契约经你确认；`npm run test` 能跑。

### F1 不依赖新接口的改进（与后端第 0–2 阶段并行）

1. **拆分组件：** `WorkspaceView`（548 行）拆成 `MetricsGrid`、`HandoffQueue`、`ProcessMonitor`、`ProductList`、`IntentChart`、`LanguageChart`、`ArchiveList`；`AgentChatPanel` 拆成 `ChatPanel`、`MessageBubble`、`WorkflowCard`、`Composer`。
2. **Pinia 状态：**
   - `useConversationStore`：会话 ID 和消息列表（按 F-D2 存进 `sessionStorage`）、发送状态、"新会话"；
   - `useDashboardStore`：看板、接管队列、最近归档。每 10 秒刷新一次，页面隐藏时暂停，本页发完消息后立即刷新；
   - `useSystemStore`：服务状态。后端第 1 阶段提供 `/status` 后就用它；在那之前退回 `/health`，并明确显示"模型状态未知"，不再写死"可用"。
3. **修复：**
   - 输入法选字时按回车不发送（判断 `event.isComposing`，或 `keyCode === 229`）；
   - 发送中禁用快捷场景按钮，也不覆盖用户正在输入的内容；
   - 422 校验错误不再显示成 `[object Object]`；超时和中止给出明确提示；
   - 补上 `public/favicon.svg`；
   - 顶栏的"系统框架已就绪"改为真实状态；
   - 回复用 `markdown-it` 渲染（F-D1）；
   - 消息 ID 改用自增计数，不再用 `Date.now()`。
4. **清理：** 删除 AstrBot 时代的兼容代码（`stringifyAgentData` 等）、没用到的 `initialized` 状态和页面过渡样式；`AppShell` 只挂载一次，不再随路由切换重新挂载。
5. **测试：** 覆盖 `request()` 的错误解析、各个 store，以及 `Composer` 的回车和输入法行为。

**验收：** 构建和测试通过；接现在的后端，演示 4 步在浏览器里走通，并截图记录；刷新页面后会话还在。

### F2 对接新接口（契约确认后开始）

先对接按契约写的模拟数据，后端第 3 阶段完成后再换成真实接口，不用干等。

1. 用 `openapi-typescript` 从 `openapi.json` 生成类型（`npm run gen:api`），删除手写的重复类型。
2. 改用以会话为中心的接口：创建会话、读取历史、发消息；"新会话""转人工""回复语言"改为调用对应的新接口。
3. 流式回复：`EventSource` 不支持 POST，所以用 `fetch` + `ReadableStream` 解析 SSE；回复逐字显示；"流程监控"显示真实的工具调用和耗时；事后分析结果到达后，再更新卡片和商家摘要。
4. 统一错误信封：按错误码给出提示，例如 `LLM_NOT_CONFIGURED` 提示"后端还没配置模型密钥"。
5. 每条消息生成 `client_message_id`；失败时提供"重试"按钮，并复用同一个 ID。
6. 接管流程（D4）：会话处于人工处理中时，聊天区显示"已转人工"，机器人不再回复；接管队列增加"标记解决"。

**验收：** 对接模拟数据时构建和测试通过；对接真实后端后，演示 4 步、流式输出、刷新恢复、接管流程都能走通。

### F3 联调与收尾

1. 后端第 3 阶段合并后，在完整环境下联调，修复对接问题。
2. 前端完全切换到新接口后，通知你可以让后端删除兼容层。
3. 更新根目录 README 的演示步骤（包括 D4 的接管流程）。

**验收：** 完整演示有截图记录；README 已更新。

## 5. 需要后端提供的东西

| 需要什么 | 由谁提供 | 什么时候要用 |
|---|---|---|
| `GET /api/v1/status` | 后端第 1 阶段 | F1 的状态显示（没有时先退回 `/health`） |
| `python -m app.scripts.export_openapi` | 后端第 1 阶段 | F2 生成类型 |
| 按契约实现的新接口 | 后端第 3 阶段 | F2 换成真实接口、F3 联调 |
| 删除兼容层 | 后端，收到负责人通知后 | F3 之后 |

## 6. 风险与对策

- **契约漂移：** 以 `api-contract.md` 为准；任何一方想改接口，都先提给负责人。
- **并行冲突：** 严格按第 1 节的文件归属；前后端各用自己的 worktree 和分支。
- **后端第 3 阶段排在最后：** F2 先对接模拟数据，F3 再集中联调，前端不用干等。
