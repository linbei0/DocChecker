def _looks_like_body_format_requirement(text: str) -> bool:
    return (
        ("中文" in text or "宋体" in text)
        and ("英文" in text or "数字" in text or "Times New Roman" in text)
        and "首行缩进" in text
        and "行距" in text
    )


def _has_explicit_non_body_target(text: str) -> bool:
    return any(
        keyword in text
        for keyword in [
            "摘要",
            "关键词",
            "一级标题",
            "二级标题",
            "三级标题",
            "目录",
            "图题",
            "图注",
            "表题",
            "表注",
            "参考文献",
        ]
    )


def _has_non_body_format_context(text: str) -> bool:
    return any(
        keyword in text
        for keyword in [
            "图题",
            "图注",
            "表题",
            "表注",
            "题注",
            "图中",
            "表中",
            "公式",
            "表达式",
            "目录",
            "参考文献",
        ]
    )
