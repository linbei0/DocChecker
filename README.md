# DocChecker

DocChecker 是一个面向学位论文和学术文档的 Word 格式检查系统。它可以接收待检查论文文档、格式规范文本或规范 Word 文档，将格式要求整理为可确认的规则集，并基于 `.docx` 的结构化内容输出带证据、位置和修改建议的检查报告。

项目当前包含 FastAPI 后端和 Vite + React 前端，重点覆盖论文提交前的格式自检、规则确认、检查任务跟踪和报告查看。

> [!NOTE]
> MVP 的核心目标是“可信检查和证据化报告”，不是静默自动改稿。规则抽取失败、文档无法解析或检查器异常都会显式暴露错误。

## 功能特性

- 上传 `.docx` 论文文档并进行格式检查。
- 支持上传 `.doc`，通过 LibreOffice 显式转换为 `.docx` 后再检查。
- 从手动输入的格式要求中抽取字体、字号、行距、缩进、页边距、标题、题注、参考文献等规则。
- 从格式规范 Word 文档中解析段落、表格、样式和示例格式，生成候选规则。
- 规则确认流程：候选规则需要用户确认后才进入正式检查。
- 检查结果包含严重程度、规则来源、期望值、实际值、定位信息、上下文片段和修改建议。
- 生成 Markdown 报告，并持久化任务、规则集和报告状态。
- 前端提供新建检查、规则模板、检查进度、报告详情和历史任务页面。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | Python 3.12, FastAPI, Pydantic, python-docx, lxml |
| 存储 | 本地文件存储, SQLite |
| 任务 | 默认内联执行；预留 RQ + Redis 配置 |
| 前端 | React 19, TypeScript, Vite, React Router, TanStack Query, Tailwind CSS |
| 测试与质量 | pytest, ruff, Vitest, TypeScript |

## 项目结构

```text
DocChecker/
├─ src/docchecker/
│  ├─ api/                 # FastAPI 接口入口
│  ├─ checkers/            # 字体、段落、页面、语义类检查器
│  ├─ core/                # 运行配置
│  ├─ domain/              # 文档、规则、任务、报告领域模型
│  ├─ parsing/             # Word / OOXML 解析
│  ├─ reports/             # 报告渲染
│  └─ services/            # 文件存储、规则抽取、状态存储、检查服务
├─ frontend/
│  ├─ src/app/             # 应用壳和路由
│  ├─ src/pages/           # 检查、规则确认、报告、模板、历史页面
│  ├─ src/features/        # API hooks 和业务能力
│  └─ src/shared/          # API client、配置、通用 UI
├─ tests/                  # 后端测试
├─ docs/                   # 产品需求和技术设计文档
├─ storage/                # 本地上传文件、报告和 SQLite 数据
├─ pyproject.toml          # 后端依赖、脚本和工具配置
└─ .env.example            # 运行配置示例
```

## 快速开始

### 1. 准备环境

需要安装：

- Python 3.12+
- Node.js 20+
- npm
- uv
- LibreOffice（仅在需要上传 `.doc` 文件时必需）

### 2. 安装后端依赖

```powershell
uv sync
```

复制环境变量示例：

```powershell
Copy-Item .env.example .env
```

默认配置使用本地规则抽取，不需要 LLM 密钥。

### 3. 启动后端 API

```powershell
uv run docchecker-api
```

后端默认监听：

```text
http://127.0.0.1:8001
```

健康检查：

```text
GET http://127.0.0.1:8001/api/health
```

### 4. 安装并启动前端

```powershell
cd frontend
npm install
npm run dev
```

Vite 会将 `/api` 请求代理到 `http://127.0.0.1:8001`。启动后在浏览器打开 Vite 输出的本地地址即可使用。

## 配置

运行配置通过仓库根目录的 `.env` 读取，变量前缀为 `DOC_CHECKER_`。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DOC_CHECKER_STORAGE_DIR` | `storage` | 上传文件和报告的本地存储目录 |
| `DOC_CHECKER_DATABASE_PATH` | `storage/docchecker.sqlite3` | SQLite 状态库路径 |
| `DOC_CHECKER_RULE_EXTRACTOR_MODE` | `local` | 规则抽取模式，支持 `local` 或 `hybrid` |
| `DOC_CHECKER_LLM_API_BASE` | 空 | OpenAI 兼容接口地址，`hybrid` 模式必填 |
| `DOC_CHECKER_LLM_API_KEY` | 空 | LLM API 密钥，`hybrid` 模式必填 |
| `DOC_CHECKER_LLM_MODEL` | 空 | LLM 模型名，`hybrid` 模式必填 |
| `DOC_CHECKER_LIBREOFFICE_COMMAND` | `soffice` | `.doc` 转 `.docx` 使用的 LibreOffice 命令 |
| `DOC_CHECKER_TASK_EXECUTION_MODE` | `inline` | 任务执行模式；`rq` 仅预留，当前设置为 `rq` 会显式报错 |
| `DOC_CHECKER_REDIS_URL` | `redis://localhost:6379/0` | 预留 Redis 地址，当前内联模式不会使用 |

> [!IMPORTANT]
> `DOC_CHECKER_RULE_EXTRACTOR_MODE=hybrid` 会调用外部 OpenAI 兼容服务。请只在确认密钥、网络和数据合规要求后启用。

## 常用 API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/documents` | 上传待检查 Word 文档 |
| `POST` | `/api/requirement-documents` | 上传格式规范 Word 文档 |
| `POST` | `/api/rulesets` | 创建正式规则集 |
| `GET` | `/api/rulesets` | 获取规则集列表 |
| `PATCH` | `/api/rulesets/{ruleset_id}` | 更新规则集 |
| `POST` | `/api/draft-rulesets` | 从文本、规范文档或模板创建草稿规则集 |
| `GET` | `/api/draft-rulesets/{draft_id}` | 获取草稿规则集 |
| `PATCH` | `/api/draft-rulesets/{draft_id}` | 更新草稿规则集 |
| `POST` | `/api/draft-rulesets/{draft_id}/publish` | 发布草稿为正式规则集 |
| `POST` | `/api/check-tasks` | 创建检查任务 |
| `GET` | `/api/check-tasks` | 获取检查任务列表 |
| `GET` | `/api/check-tasks/{task_id}` | 获取检查任务详情 |
| `GET` | `/api/reports/{report_id}` | 获取结构化检查报告 |
| `GET` | `/api/reports/{report_id}/export` | 获取 Markdown 报告路径 |

## 开发命令

后端：

```powershell
uv run pytest
uv run ruff check .
```

前端：

```powershell
cd frontend
npm run typecheck
npm run test
npm run build
```

## 典型工作流

1. 上传待检查论文文档。
2. 通过手动输入、上传规范 Word 文档或复制已有模板创建草稿规则集。
3. 在前端确认、编辑或禁用候选规则。
4. 发布正式规则集。
5. 创建检查任务并等待执行完成。
6. 查看结构化报告，按位置、严重程度和规则来源处理格式问题。
7. 导出 Markdown 报告用于归档或交付。

## 当前边界

- `.docx` 是主要检查格式；`.doc` 依赖本机 LibreOffice 转换链路。
- 默认规则抽取为本地确定性解析，复杂自然语言规范可能进入待确认或不支持列表。
- RQ + Redis 已保留配置项，但默认任务执行模式为 `inline`。
- 检查覆盖重点是 Word 格式结构、页面设置、段落格式、字体、标题、目录、题注和参考文献等论文格式场景。
