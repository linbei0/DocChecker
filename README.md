# DocChecker Backend

论文 Word 格式检查系统后端工程。当前实现聚焦 MVP 的可信检查闭环：

- FastAPI API 服务
- `.docx` 文件校验与基础解析，`.doc` 文件经 LibreOffice 显式转换后复用同一检查链路
- Pydantic v2 规则、文档模型和 finding 模型
- 页面设置、字体、段落检查器
- Markdown 报告生成
- uv 虚拟环境与 pytest/ruff 工程化检查

## `.doc` 支持

`.doc` 是旧版 Word 二进制格式，服务端不直接解析其版式结构。上传 `.doc` 后，后端会调用
LibreOffice `soffice` 将其显式转换为临时 `.docx`，再执行现有解析与检查流程。

可通过环境变量配置转换命令和超时：

```bash
DOC_CHECKER_LIBREOFFICE_COMMAND=soffice
DOC_CHECKER_LIBREOFFICE_CONVERSION_TIMEOUT_SECONDS=60
```

将 `DOC_CHECKER_LIBREOFFICE_CONVERSION_TIMEOUT_SECONDS` 设为 `0` 可关闭转换超时。

## 本地启动

```bash
uv sync
uv run uvicorn docchecker.api.main:app --reload
uv run uvicorn docchecker.api.main:app --reload --port 8001
```

## 运行检查

```bash
uv run ruff check .
uv run pytest
```

## 约束

- 正式支持 `.docx`，以及可被 LibreOffice 成功转换为 `.docx` 的 `.doc`。
- `.doc` 转换是显式依赖；部署环境需要安装 LibreOffice 或配置 `soffice` 命令路径。
- 无法可靠判断的格式项会作为解析警告或 unknown 结果暴露，不生成伪造结论。
- 论文正文不会被发送给外部大模型。
