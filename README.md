# DocChecker Backend

论文 Word 格式检查系统后端工程。当前实现聚焦 MVP 的可信检查闭环：

- FastAPI API 服务
- `.docx` 文件校验与基础解析
- Pydantic v2 规则、文档模型和 finding 模型
- 页面设置、字体、段落检查器
- Markdown 报告生成
- uv 虚拟环境与 pytest/ruff 工程化检查

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

- MVP 只正式支持 `.docx`。
- `.doc` 不做服务端静默转换。
- 无法可靠判断的格式项会作为解析警告或 unknown 结果暴露，不生成伪造结论。
- 论文正文不会被发送给外部大模型。
