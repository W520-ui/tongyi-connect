# 第 1 阶段工作记录

## 起点与恢复

- 分支：`backend/phase-1`，从第 0 阶段交付 `17b9b1a` 创建，用户已明确回复“继续”。
- 唯一有效说明仍是 `D:\10178\Projects\tongyi-connect-frontend\docs\backend-prompt.md`，本阶段只执行其第 1 阶段。
- 用户追加要求：Mars 必须是明确的工具参数校验失败（失败标记、错误信息），不能用 `unconfirmed` 蒙混通过；前端 CI 在构建之后执行 `npm run test --if-present`。
- Git 起点干净；不修改前端 worktree、不推送、不改写历史。
- 工作顺序：先提交追加的验收要求；迁移商品/护栏/归档统计/HTTP 展示职责；实现协议与类型化工具循环；用 ConversationService 和 lifespan 接回旧 API；迁移测试并补齐健壮性、生命周期和导出验证；完整验收和分逻辑提交后停下。
- 目标边界：`api → services → agent 或 repositories → domain`，公共配置在 `core`；Agent 不依赖 HTTP、业务服务或仓储。
- 本阶段保留旧 SQLite 表，仅增加所需列和失败计数，统一新表及接管状态机留给第 2 阶段。
- 恢复时先核对 `git status --short --branch`、`git log -6 --oneline` 和本记录，不要重置工作区；第 2 阶段仍需再次回复“继续”。

## 当前进度

正在实施。第 0 阶段的完整验收记录见 `PHASE_0.md`。
