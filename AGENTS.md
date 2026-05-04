# AGENTS.md

## 项目概览

DocChecker 是一个面向学位论文和学术文档的 Word 格式检查系统。后端负责 Word 上传、`.doc` 到 `.docx` 转换、规则抽取、格式检查、报告生成和状态持久化；前端负责检查任务流、规则确认、模板管理、历史任务和报告查看。

技术栈：

- 后端：Python 3.12+, FastAPI, Pydantic v2, python-docx, lxml, SQLite。
- 前端：React 19, TypeScript, Vite, React Router, TanStack Query, Tailwind CSS。
- 工具：uv, pytest, ruff, npm, Vitest, TypeScript。

## 代码结构

- `src/docchecker/api/`：FastAPI 入口和 HTTP 接口。
- `src/docchecker/checkers/`：字体、段落、页面设置、目录、题注、参考文献、结构等检查器。
- `src/docchecker/core/`：运行配置，读取 `DOC_CHECKER_` 前缀环境变量。
- `src/docchecker/domain/`：文档、规则、任务、报告等 Pydantic 领域模型。
- `src/docchecker/parsing/`：`.docx` / OOXML 解析逻辑。
- `src/docchecker/reports/`：Markdown 报告渲染。
- `src/docchecker/services/`：文件存储、状态存储、规则抽取、Word 预处理和检查服务。
- `frontend/src/app/`：应用壳和路由。
- `frontend/src/pages/`：页面级功能。
- `frontend/src/features/`：业务 API 与 hooks。
- `frontend/src/shared/`：共享 API client、配置、UI 和工具函数。
- `tests/`：后端测试。
- `docs/`：产品需求和技术设计文档。

## 环境与依赖

首次设置：

```powershell
uv sync
Copy-Item .env.example .env
cd frontend
npm install
```

本地规则抽取默认不需要外部 LLM。只有启用 `DOC_CHECKER_RULE_EXTRACTOR_MODE=hybrid` 时，才需要配置：

- `DOC_CHECKER_LLM_API_BASE`
- `DOC_CHECKER_LLM_API_KEY`
- `DOC_CHECKER_LLM_MODEL`

`.doc` 上传依赖 LibreOffice 转换链路，默认命令是 `soffice`，可通过 `DOC_CHECKER_LIBREOFFICE_COMMAND` 覆盖。

## 开发服务

后端 API：

```powershell
uv run docchecker-api
```

默认监听 `http://127.0.0.1:8001`。前端 Vite 代理会把 `/api` 请求转发到该地址。

前端开发服务：

```powershell
cd frontend
npm run dev
```

## 测试与验证

提交或交付前运行完整检查：

```powershell
uv run pytest
uv run ruff check .
cd frontend
npm run typecheck
npm run test -- --run
npm run build
```

后端可按文件或测试名聚焦运行：

```powershell
uv run pytest tests/test_rule_extractor.py
uv run pytest -k "rule_extractor"
```

前端可按 Vitest 测试名聚焦运行：

```powershell
cd frontend
npm run test -- --run -t "test name"
```

若只改文档，仍需至少确认仓库状态和相关文档内容；涉及代码、配置、依赖、构建或前端页面时必须运行对应自动化检查。

## 编码约定

- 遵循现有目录边界和领域模型，不随意跨层调用。
- 后端规则和检查逻辑应让失败显式暴露，不添加静默兜底、伪成功、mock 成功路径或吞错逻辑。
- 不为“让流程跑通”新增隐藏限制、隐式降级、最大轮次、默认跳过或自动忽略规则。
- `.docx` 是主要解析格式；`.doc` 必须通过显式 LibreOffice 转换后复用同一检查链路。
- 检查报告必须保留规则来源、期望值、实际值、位置、严重程度和上下文证据。
- 新增或修改核心逻辑时同步补充测试，优先覆盖真实边界和失败路径。
- Python 使用 Ruff 配置：行宽 100，目标版本 `py312`，启用 `E`, `F`, `I`, `UP`, `B`, `SIM`, `C4`。
- 前端保持现有 React + TypeScript + TanStack Query + Tailwind 组织方式，复用 `shared` 和 `features` 下已有抽象。
- 注释使用简体中文，仅用于关键流程、核心逻辑或不易直接理解的实现细节。

## 文件操作与工具偏好

- 搜索代码优先使用 `code-index-mcp`：`set_project_path`、`find_files`、`search_code_advanced`、`get_file_summary`、`refresh_index`。
- 首次进入仓库或索引异常时，设置项目路径为仓库根目录：`E:\python-project\DocChecker`。
- 编辑文件优先使用 `apply_patch`，避免 PowerShell 写文件造成编码问题。
- 读取本地文件优先使用可用的 MCP 文件工具；若工具只返回元数据或读取失败，可使用只读 shell 命令补充上下文。
- shell 默认使用 `pwsh` / `pwsh.exe`，不要使用 Windows PowerShell 5.1，除非用户明确要求或 `pwsh` 不可用。
- 不使用破坏性 Git 命令。除非用户明确要求，Git 仅做只读操作。

## 配置与数据

运行配置由仓库根目录 `.env` 提供，字段定义见 `src/docchecker/core/config.py` 和 `.env.example`。

常用变量：

- `DOC_CHECKER_STORAGE_DIR`
- `DOC_CHECKER_DATABASE_PATH`
- `DOC_CHECKER_RULE_EXTRACTOR_MODE`
- `DOC_CHECKER_LLM_API_BASE`
- `DOC_CHECKER_LLM_API_KEY`
- `DOC_CHECKER_LLM_MODEL`
- `DOC_CHECKER_LIBREOFFICE_COMMAND`
- `DOC_CHECKER_TASK_EXECUTION_MODE`
- `DOC_CHECKER_REDIS_URL`

不要提交 `.env` 或真实密钥。`storage/` 是本地上传文件、报告和 SQLite 数据目录，改动前确认是否是用户数据或测试夹具。

## API 工作流

核心接口在 `src/docchecker/api/main.py`：

- `POST /api/documents`：上传待检查 Word 文档。
- `POST /api/requirement-documents`：上传格式规范 Word 文档。
- `POST /api/draft-rulesets`：从文本、规范文档或模板创建草稿规则集。
- `PATCH /api/draft-rulesets/{draft_id}`：确认或编辑候选规则。
- `POST /api/draft-rulesets/{draft_id}/publish`：发布正式规则集。
- `POST /api/check-tasks`：创建检查任务。
- `GET /api/reports/{report_id}`：读取结构化报告。
- `GET /api/reports/{report_id}/export`：获取 Markdown 报告路径。

实现接口变更时，同步检查前端 `frontend/src/features/**/api.ts`、hooks、页面路由和 Zod schema。

## 前端注意事项

- Vite 代理在 `frontend/vite.config.ts`，默认目标是 `http://127.0.0.1:8001`。
- API 请求封装在 `frontend/src/shared/api/client.ts`。
- 环境配置封装在 `frontend/src/shared/config/env.ts`。
- 页面路由在 `frontend/src/app/router.tsx`。
- UI 改动需要验证桌面和移动宽度下无文本溢出、按钮挤压或布局重叠。

## 常见风险

- Word 格式可能来自直接格式、样式继承、默认样式或 OOXML 节属性，不能只看纯文本。
- 规范文档可能混合自然语言、表格和示例段落，抽取结果必须保留来源并允许用户确认。
- LLM hybrid 模式涉及外部服务和隐私边界，默认不要启用或依赖它完成测试。
- `.doc` 转换失败应返回清晰错误，不能伪装为 `.docx` 检查成功。
- 前端 build 可能出现 chunk size warning；这是体积警告，不等同于构建失败，但涉及性能优化时需要处理。

