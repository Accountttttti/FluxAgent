"""文件系统 + 搜索 + 补丁工具：复刻 nanobot 的 filesystem / search / apply_patch（简化版）。

工作区统一为项目根目录（backend 的上一级）。所有路径都相对这个根解析，
并强制「不能逃出项目根」，防止模型用 ../ 读或写项目外的文件。

砍掉的复杂部分：glob 高级匹配、文件类型过滤（docx/pdf 全文抽取）、
扫描预算/超时、路径排序分页、软链接跟随。
"""
import os
import re
from pathlib import Path

# 项目根目录 = backend 的上一级（F:\Code\FluxAgent）
WORKSPACE = Path(__file__).parent.parent

# find_files / grep 遍历时要跳过的目录名
IGNORE_DIRS = {".git", ".venv", "node_modules", "__pycache__", "reference", ".claude", "memory", "dist", "build"}

MAX_GREP_FILE_BYTES = 2_000_000
MAX_RESULTS = 200


def resolve(path: str) -> Path:
    """把路径解析到工作区内，越界则抛 ValueError。"""
    p = Path(path)
    target = p.resolve() if p.is_absolute() else (WORKSPACE / p).resolve()
    root = WORKSPACE.resolve()
    if target == root or root in target.parents:
        return target
    raise ValueError("只允许访问项目目录内的文件")


def write_file(path: str, content: str) -> str:
    """写文件（新建或覆盖），自动创建父目录。"""
    try:
        target = resolve(path)
    except ValueError as exc:
        return f"错误：{exc}"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"已写入 {path}（{len(content)} 字符）"
    except Exception as exc:
        return f"错误：写入失败：{exc}"


def edit_file(path: str, old_text: str, new_text: str) -> str:
    """精确替换文件里唯一的一处 old_text 为 new_text。"""
    try:
        target = resolve(path)
    except ValueError as exc:
        return f"错误：{exc}"
    try:
        text = target.read_text(encoding="utf-8")
    except Exception as exc:
        return f"错误：读取失败：{exc}"
    occurrences = text.count(old_text)
    if occurrences == 0:
        return "错误：old_text 在文件里没找到"
    if occurrences > 1:
        return f"错误：old_text 出现了 {occurrences} 次，请提供更唯一的文本"
    target.write_text(text.replace(old_text, new_text), encoding="utf-8")
    return f"已编辑 {path}（替换 1 处）"


def list_dir(path: str = ".") -> str:
    """列出目录内容，目录后面加 / 标记。"""
    try:
        target = resolve(path)
    except ValueError as exc:
        return f"错误：{exc}"
    if not target.exists():
        return "错误：路径不存在"
    if target.is_file():
        return target.name
    entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    if not entries:
        return "（空目录）"
    return "\n".join(e.name + ("/" if e.is_dir() else "") for e in entries)


def find_files(query: str, path: str = ".") -> str:
    """按文件名片段找文件（大小写不敏感），返回相对路径。"""
    try:
        root = resolve(path)
    except ValueError as exc:
        return f"错误：{exc}"
    if not root.exists():
        return "错误：路径不存在"
    if root.is_file():
        return root.name if query.lower() in root.name.lower() else "（没有匹配的文件）"

    matches: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
        for fn in sorted(filenames):
            if query.lower() in fn.lower():
                matches.append(str((Path(dirpath) / fn).relative_to(WORKSPACE.resolve())))
                if len(matches) >= MAX_RESULTS:
                    return "\n".join(matches)
    return "\n".join(matches) if matches else "（没有匹配的文件）"


def grep(pattern: str, path: str = ".", case_insensitive: bool = False) -> str:
    """在文件内容里搜正则，返回「文件:行号: 内容」。跳过二进制/超大文件。"""
    try:
        root = resolve(path)
    except ValueError as exc:
        return f"错误：{exc}"
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        rx = re.compile(pattern, flags)
    except re.error as exc:
        return f"错误：正则表达式无效：{exc}"

    matches: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
        for fn in sorted(filenames):
            full = Path(dirpath) / fn
            try:
                if full.stat().st_size > MAX_GREP_FILE_BYTES:
                    continue
                text = full.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = full.relative_to(WORKSPACE.resolve())
            for i, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    matches.append(f"{rel}:{i}: {line[:200]}")
                    if len(matches) >= MAX_RESULTS:
                        return "\n".join(matches)
    return "\n".join(matches) if matches else "（没有匹配的内容）"


def _append_with_newline(target: Path, content: str) -> None:
    """追加内容，必要时补一个换行，避免和上一行粘在一起。"""
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if existing and not existing.endswith("\n") and content and not content.startswith("\n"):
        content = "\n" + content
    with open(target, "a", encoding="utf-8") as f:
        f.write(content)


def apply_patch(edits: list[dict], dry_run: bool = False) -> str:
    """按顺序应用一组结构化编辑。每条 edit：{path, action, old_text, new_text}。

    action='replace' 替换唯一一处 old_text；action='add' 新建或追加 new_text。
    """
    if not edits:
        return "错误：edits 不能为空"
    results: list[str] = []
    for edit in edits:
        if not isinstance(edit, dict):
            results.append("错误：每条 edit 必须是对象")
            continue
        path = edit.get("path")
        action = edit.get("action")
        if not path or action not in ("replace", "add"):
            results.append("错误：每条 edit 需要 path 和 action（replace/add）")
            continue
        try:
            target = resolve(path)
        except ValueError as exc:
            results.append(f"错误：{path}: {exc}")
            continue

        if action == "add":
            content = edit.get("new_text", "")
            if dry_run:
                results.append(f"[dry-run] 将追加到 {path}")
                continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                _append_with_newline(target, content)
                results.append(f"已追加到 {path}")
            except Exception as exc:
                results.append(f"错误：{path}: {exc}")
        else:  # replace
            old_text = edit.get("old_text", "")
            new_text = edit.get("new_text", "")
            if not old_text:
                results.append(f"错误：{path}: replace 需要 old_text")
                continue
            try:
                text = target.read_text(encoding="utf-8")
            except Exception as exc:
                results.append(f"错误：{path}: 读取失败 {exc}")
                continue
            occurrences = text.count(old_text)
            if occurrences == 0:
                results.append(f"错误：{path}: old_text 没找到")
            elif occurrences > 1:
                results.append(f"错误：{path}: old_text 出现 {occurrences} 次，不唯一")
            elif dry_run:
                results.append(f"[dry-run] 将替换 {path} 的 1 处")
            else:
                target.write_text(text.replace(old_text, new_text), encoding="utf-8")
                results.append(f"已替换 {path} 的 1 处")
    return "\n".join(results)
