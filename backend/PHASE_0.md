# 第 0 阶段交付记录：安全网

## 起点与恢复

- 说明来源：`D:\10178\Projects\tongyi-connect-frontend\docs\backend-prompt.md`，已完整阅读。
- 后端目录：`D:\10178\Projects\tongyi-connect`；分支：`backend/phase-0`。
- 起点：`e6a7ffaf1277715f1496e4e4fd1a3222c736d303`，与 `docs/refactor-plan` 相同。
- 接手时已经有 `backend/pyproject.toml` 的开发依赖改动和未跟踪的 `backend/uv.lock`；已核对，符合第 0 阶段要求，沿用。
- 已完整阅读后端代码、测试、两份 README、架构评审和旧前端 `src/services/`。
- 已执行指定的 Python 3.12 虚拟环境创建及 `uv pip install -e ".[dev]"`。
- 原始 ruff 基线：26 项问题。原始前端构建因尚未安装 `vue-tsc` 失败，需先在后端所在的主 worktree 执行 `npm ci`。
- 当前状态：第 0 阶段已完成；停在 `backend/phase-0`，等待负责人回复“继续”。
- 恢复前先执行 `git status --short --branch`、`git log -5 --oneline`，核对本文件。不得修改前端 worktree 或推送；第 1 阶段需负责人回复“继续”。

## 1. 改动与提交

- 依赖与文档：保留原 Python ≥ 3.11 要求，建立 Python 3.12.11 环境；沿用接手时的授权开发依赖并提交 `uv.lock`；README 改用 uv，补充锁文件安装、检查、测试和真实模型演示步骤。
- 配置与存储：新增 `WORKFLOW_DB_PATH`；默认仍为 `backend/data/workflow.db`，相对路径锚定到 `backend/`。咨询归档和会话存储使用同一个配置，数据结构和业务行为保持原样。
- 测试：保留 22 项原有 unittest；导入应用前就使用临时数据库；各测试运行时使用独立临时库。增加 18 项接口测试、3 项路径配置测试、1 项四步演示测试，以及 30 项缺陷/真阳性用例。
- 契约：检查现有请求字段、响应信封、`AgentWorkflowData` 的 18 项字段及类型；覆盖健康、商品、看板、最近归档、接管确认、参数校验与模型错误路径。未来只允许新增字段，不能删改现有字段。
- 缺陷：说明中的 1–12 全部复现为测试，共 24 个严格预期失败；另保留 6 个通过的真阳性/已知西班牙物流用例。`raises=AssertionError` 防止模型脚本耗尽、程序异常等被当成已知缺陷。
- CI：新增 `.github/workflows/ci.yml`，后端执行锁文件检查、ruff 和全部测试，前端独立执行 `npm ci` 与 `npm run build`。
- lint 与格式：修复原始 26 项 lint 问题；`ruff format` 单独提交。格式化前后比较 46 个应用/测试 Python 文件的 AST 摘要，全部一致。

提交依次为：

| 提交 | 内容 |
|---|---|
| `260ad06` | `build(backend): lock Python dependencies and document uv workflow` |
| `086fc24` | `test(backend): establish isolated API and defect regression safety net` |
| `8ec9fbe` | `style(backend): apply ruff formatting in a dedicated commit` |
| 本文件的交付提交 | `docs(backend): record phase 0 validation and recovery checkpoint` |

没有推送、合并或改写历史。改动只位于 `backend/**` 和 `.github/workflows/**`。未修改前端代码或前端 worktree；在主 worktree 安装前端依赖并生成的构建产物由现有忽略规则处理。

## 2. 验证结果

下列后端命令在 `D:\10178\Projects\tongyi-connect\backend` 执行：

| 命令 | 关键输出 |
|---|---|
| `uv sync --frozen --extra dev` | `Audited 37 packages`，退出码 0 |
| `uv lock --check` | `Resolved 38 packages`，退出码 0 |
| `uv run --frozen --extra dev ruff check .` | `All checks passed!` |
| `uv run --frozen --extra dev ruff format --check .` | `48 files already formatted` |
| `uv run --frozen --extra dev pytest` | 收集 74 项；`50 passed, 24 xfailed, 1 warning` |
| `uv run --extra dev python -m unittest discover -s tests -v` | 原有 `Ran 22 tests`、`OK` |

前端命令在后端所在的主 worktree 根目录执行：

| 命令 | 关键输出 |
|---|---|
| `npm ci` | 安装 95 个包；`found 0 vulnerabilities` |
| `npm run build` | `vue-tsc -b && vite build` 通过；`45 modules transformed`、`built in 205ms` |

`git diff --check docs/refactor-plan` 通过；检查改动文件列表全部在授权目录内。验收后 `backend/data/` 仍不存在，测试没有生成真实数据库。

测试的唯一警告来自锁定版本的 Starlette TestClient：当前 httpx 适配被标为弃用。没有隐藏警告，也没有因此添加未获授权的 `httpx2`；现有测试均通过。

## 3. 与说明不一致的地方

没有阶段范围、接口形状或文件归属方面的偏离。分支已经由之前的工作建立，起点仍是指定的 `e6a7ffa`，因此直接继续该分支，没有重复创建或改写它。

CI 配置已提交，相同命令已在本机验证；遵守不推送的要求，因此没有声称远程 GitHub Actions 已运行。真实模型调用没有执行，本阶段按要求交付自动化假模型验证和真实模型的手动步骤。

API 测试通过依赖覆盖和临时资源隔离现有模块级单例，资源由测试夹具关闭；这不代表已经完成第 1 阶段要求的 lifespan 资源创建、依赖边界或单例移除。

## 4. TODO(owner) 与待决定问题

本阶段没有新增 `TODO(owner)`，没有新增会影响业务行为的选择。D2 已有的真实可配送范围确认仍由负责人处理；本阶段不修改物流业务行为。已知缺陷 1–11 留待第 1 阶段，12 留待第 2 阶段。

## 5. 演示验证

`tests/test_demo_smoke.py::test_readme_demo_four_steps` 已在全部测试中通过。用脚本化假模型完成：

1. 英文回复要求和西班牙配送咨询 → 检索耳机、查询 ES 物流、返回英文。
2. 同一会话追问物流 → 恢复 `headset-pro` 上下文，保留 5–8 个工作日时效。
3. 登记耳机无法开机售后 → 调用 `after_sales_record`，队列出现 1 条接管记录，商家确认后待处理变成 0。
4. 看板、归档与健康检查 → 咨询 3、接管 1、失败 0、解决率 66.7%，语言分布为英文 1/中文 2，历史 6 条，两轮物流意图和一轮售后意图均被归档。

需要单独重跑演示时：`uv run --extra dev pytest tests/test_demo_smoke.py -v`。

真实模型手动步骤（未执行）：在后端 `.env` 配置模型地址、名称和密钥；主 worktree 根目录启动 `npm run dev`，打开 `http://127.0.0.1:5173/`。依次发送“请用英文回复：星云降噪耳机 Pro 支持发往西班牙吗？”、“那它的物流要多久？”、“客户说耳机收到后无法开机，帮我登记售后”，检查回复与商品事实、确认接管，再检查咨询累计增加 3、接管增加 1、最近归档及健康状态。完整步骤见 `README.md` 的“真实模型手动验证”。

## 下一阶段的恢复入口

负责人回复“继续”后，先检查 Git 状态与本文件，再从本阶段分支拉出 `backend/phase-1`。按唯一有效的 `backend-prompt.md` 第 1 阶段顺序实施；不要使用旧版 `docs/refactor-prompt.md` 或 `docs/frontend-plan.md`。进入第 1 阶段后，修复缺陷 1–11 并移除对应预期失败标记，保留第 2 阶段的缺陷 12 标记；增加工具循环健壮性和资源生命周期测试，并提前交付 status 与 OpenAPI 导出。
