# 前端重写计划 v2（Claude 负责）

- **决定（2026-11-14，负责人确认）：** 前端从零重写；客户窗口和商家控制台完全分开；视觉重新设计；组件库由 Claude 选定。
- **分工：** 后端由 GPT 按 `docs/backend-prompt.md` 重构；前端只按其中的附录 A（接口契约 v0.1）对接，不使用任何旧接口。
- **分支：** `frontend/v2`（在 worktree `D:\10178\Projects\tongyi-connect-frontend` 里），不推送，由负责人合并。

## 1. 技术选型

| 方面 | 选择 | 理由 |
|---|---|---|
| 框架 | Vue 3 + TypeScript + Vite + Vue Router + Pinia | 沿用现有技术栈 |
| 组件库 | shadcn-vue（Reka UI + Tailwind CSS v4，经典 vega 风格，中性灰底） | 负责人认为 Naive UI 太常见，要现代风格、不用渐变。shadcn-vue 的组件代码放在我们自己的仓库里，外观完全可控 |
| 视觉 | 纯色、细边框、基本不用阴影；主按钮近黑色；品牌青绿只用于标志、状态点等少数点缀 | 2026-11-14 负责人确认效果图 |
| 图标 | lucide-vue-next | 线条统一、仍在维护 |
| 字体 | Inter（@fontsource-variable，本地打包）+ 系统中文字体 | 不依赖外部 CDN |
| 模拟后端 | Vite 开发服务器中间件，按附录 A 实现 | 不加运行时依赖，SSE 行为和真实后端一致；用 `vite --mode mock` 启动 |
| 测试 | Vitest + Vue Test Utils + jsdom | F0 已搭好 |

## 2. 页面

**客户窗口** `/chat`：面向海外客户的聊天页，以后可以改成网站挂件。

- 界面文字支持中文、英文、西语，切换时同时设置会话的回复语言；
- 流式回复、商品小卡片、"转人工"、"新会话"、转人工后的状态提示；
- 不显示任何内部信息（意图、轨迹、商家摘要）。

**商家控制台** `/console/*`：

- 收件箱 `/console/inbox`：左边是工单列表（待接管 / 处理中 / 已解决），右边是选中会话的详情，包括中文摘要、对话记录、Agent 轨迹、确认接管、标记解决；
- 数据看板 `/console/dashboard`：关键指标、意图分布、语言分布、最近咨询；
- 商品资料 `/console/catalog`、系统状态 `/console/system`；
- 支持深色模式。

## 3. 目录

```text
src/
├── api/          附录 A 的类型、请求封装、SSE 客户端、各资源的接口函数
├── stores/       Pinia：conversation（客户窗口）、inbox、dashboard、system
├── theme/        Naive UI 主题（浅色 / 深色）
├── i18n/         客户窗口的三语文案
├── layouts/      ConsoleLayout
├── pages/        chat/、console/
├── components/   chat/、console/
└── fixtures/     原型阶段的演示数据（接上模拟后端后删除）
mock/             Vite 模拟后端（只在 --mode mock 下启用）
```

## 4. 阶段

1. **V1 视觉原型：** 主题、两个页面的布局和组件，先用 `fixtures/` 里的演示数据。截图给负责人确认视觉。
2. **V2 数据层：** `api/`（类型、错误信封、SSE 解析：轮次重置、心跳超时、幂等重试）、Pinia store、`mock/` 模拟后端。页面改为走真实的数据流，删掉 `fixtures/`。
3. **V3 完整功能：** 收件箱的确认和解决、看板定时刷新、历史恢复、错误码提示、深色模式、移动端适配。
4. **V4 联调：** 后端第 3 阶段完成后，换成真实接口，跑通演示流程，更新根目录 README。

每个阶段都要求：`npm run build` 和 `npm run test` 通过，并在内置浏览器里截图验证。

## 5. 需要后端提供的东西

| 需要什么 | 什么时候要用 |
|---|---|
| `GET /api/v1/status`、`python -m app.scripts.export_openapi`（后端第 1 阶段） | V3 生成类型、核对契约 |
| 附录 A 的全部新接口（后端第 3 阶段） | V4 联调 |
