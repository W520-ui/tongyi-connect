# 前后端本地集成记录

## 当前工作目录和分支

- 集成目录：D:\10178\Projects\tongyi-connect
- 集成分支：codex/front-back-integration
- 后端来源：backend/phase-2，a53f6ae
- 前端来源：frontend/v2，63428e6
- 共同起点：e6a7ffa
- 合并提交：4ab56b6（两个来源均保留在提交历史中）
- 启动修复：6af0181（Vite 显式监听 127.0.0.1）

本次由负责人请求合并。原 backend/phase-2、frontend/v2 和 frontend worktree 都保留，不推送、不改写历史、不删除文件夹。后续使用主集成目录启动项目即可。

## 合并内容与保留检查

双方已提交的改动没有合并冲突：前端的新页面、shadcn-vue 组件、三语文案、主题、类型与 Vitest 配置进入主目录；后端第 0–2 阶段的代码、数据库迁移、测试、评测、CI 和 .gitignore 原样保留。

用 Git 对比验证：

```powershell
git diff backend/phase-2 HEAD -- backend .github/workflows .gitignore
git diff frontend/v2 HEAD -- src public index.html components.json package.json package-lock.json tsconfig.app.json tsconfig.json docs/frontend-plan.md docs/api-contract.md
```

两组对比均无差异。Vite 配置的唯一新增改动为 server.host，说明见下节。根 README 已更正为当前集成状态，删除已不存在的旧模块描述和已经接通真实界面的错误说明。

原 frontend worktree 中未提交的 docs/backend-prompt.md 和 docs/design/ 的 14 张 PNG 截图已复制到主目录，逐个校验 SHA-256 相等，来源文件保持原样。复制内容作为项目任务和设计资料保存；.claude/settings.json 等 worktree 本地配置留在原位置。

## 启动修复

Vite 默认监听 localhost，Node 在本机优先解析到 IPv6。联合启动日志显示 Vite 就绪，但本地连接 IPv6 返回错误，127.0.0.1:5173 也不可达；同一次启动的后端 127.0.0.1:8000 和直接 status 请求正常。

按 Vite 8 官方 server.host 说明，显式设置 `host: '127.0.0.1'`。修复后开发服务器地址与项目文档和后端代理地址一致，联合启动检查通过。未修改前端页面、后端接口或模型行为。

主目录执行：

```powershell
npm ci
npm run dev
```

打开 http://127.0.0.1:5173/chat 或 http://127.0.0.1:5173/console/inbox。已保留的 backend/.venv 可继续使用；依赖安装和配置见根 README 及 backend/README.md。

## 验证结果

2026-11-15 在集成目录验证：

| 检查 | 结果 |
|---|---|
| npm ci | 锁文件安装成功，198 个包新增，205 个包审计 |
| npm run build | vue-tsc 和 Vite 成功；2860 个模块，最终构建 921ms |
| npm run test --if-present | 实际运行 Vitest，3 个测试文件、11 项测试通过，6.49s |
| uv sync --frozen --extra dev | 成功，43 个包 |
| uv lock --check | 成功 |
| ruff check . | All checks passed |
| ruff format --check . | 91 files already formatted |
| 完整 pytest | 176 passed，1 warning，54.77s |
| Git 范围和空白检查 | 通过，后端保留对比无差异，原分支保持不变 |

后端测试用与阶段 2 相同的命令：

```powershell
$env:PYTHONIOENCODING = "utf-8"
uv run --frozen --extra dev pytest -q -o addopts='' --tb=short
```

唯一后端 warning 是现有 Starlette TestClient 对 httpx 的弃用提示。

npm 审计报告 5 项 moderate、0 项 high/critical，涉及 @vue/test-utils 及 editorconfig、glob、js-beautify、minimatch 的开发依赖链。建议修复会改变前端已锁定的依赖版本，本次保持原锁文件，记录该结果，没有执行 npm audit fix --force。

联合启动使用与 npm run dev 相同的 scripts/dev-all.mjs，指定临时 DATABASE_URL 和空模型密钥：

- FastAPI 与 Vite 均成功启动；
- 客户窗口、收件箱、看板、商品与系统共 5 个 SPA 路径返回 200；
- main.ts、ChatPage.vue、InboxPage.vue 开发模块返回 200；
- 经 Vite 代理的 /api/v1/status 返回 200，db_ok=true、模型未配置；
- 商品接口返回 3 个真实数据库种子商品；
- 经代理的普通聊天返回预期的 503/LLM_NOT_CONFIGURED；
- 自有 Node/Python 进程树已关闭，5173 和 8000 均释放，临时数据库删除，真实 backend/data 未创建。

这验证了共同启动和 API 代理，不代表新前端已经调用这些接口。未进行真实模型调用。

## 尚未完成的接口联调

前端来源分支当前仍是视觉原型：

- 聊天页模拟回复，数据来自 fixtures；
- 收件箱的确认与解决只修改本地状态；
- 看板、商品与系统页显示样例数据；
- api/ 目前只有类型，没有请求封装或 SSE 客户端。

后端已完成第 2 阶段，保留旧接口，但新会话、工单、历史与 SSE HTTP 入口属于尚未开始的第 3 阶段。配置模型密钥不会自动使新界面连接后端。

后续按 docs/backend-prompt.md 附录 A 和 docs/frontend-plan.md 完成新接口、前端数据层与联调。本次只合并现有成果并修复共同启动，不宣称已完成真实客服闭环，也未进入第 3 阶段。

## 恢复入口

```powershell
cd D:\10178\Projects\tongyi-connect
git status --short --branch
git log --oneline -6
git worktree list
```

确认当前是 codex/front-back-integration，再查看本记录。源 worktree 中的未提交资料仍保留，不要因主目录已有副本而直接删除源目录或重置原分支。完整集成提交列表可用 `git log --oneline backend/phase-2..codex/front-back-integration` 查看；包含前端历史及本次合并、启动修复、资料与记录提交。
