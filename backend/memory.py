"""记忆存储：复刻 nanobot 的 MemoryStore（简化版）。

nanobot 里「长期记忆」就是一个 MEMORY.md 文件，存用户信息、偏好、项目上下文等
「跨会话都要记住」的事实。每个会话开始时把它的内容注入系统提示词；模型学到新
东西时，用 save_memory 工具写回去。

隔离：nanobot 用 workspace 把不同用户的记忆分开。这里照做——每个用户一个子目录
`memory/{user_id}/`，默认用户是 "default"。这样多个用户互不干扰（多用户时前端
把用户 id 传给后端，后端 set_user 后读写的就是该用户自己的记忆）。
"""
import json
from datetime import datetime
from pathlib import Path

from gitstore import GitStore

MEMORY_ROOT = Path(__file__).parent / "memory"

# 当前用户 id。单用户默认 "default"；多用户时由 chat.py 在每个请求开头 set_user。
_current_user = "default"


def set_user(user_id: str | None) -> None:
    """设置当前请求的用户 id。chat.py 在每个请求开头调用。"""
    global _current_user
    _current_user = (user_id or "").strip() or "default"


def _dir() -> Path:
    """当前用户自己的记忆目录（不存在则创建）。"""
    d = MEMORY_ROOT / _current_user
    d.mkdir(parents=True, exist_ok=True)
    return d


def read() -> str:
    """读取当前用户的长期记忆全文（不存在则返回空串）。"""
    f = _dir() / "MEMORY.md"
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def write(content: str, commit_message: str = "memory: update") -> str:
    """用新内容覆盖当前用户的长期记忆文件，并自动 git 提交一次版本。

    每次记忆变更都是一个 commit，这样能看记忆是怎么演变的、也能回滚。
    """
    (_dir() / "MEMORY.md").write_text(content, encoding="utf-8")
    _git_commit(commit_message)
    return "已保存到长期记忆"


def _git_commit(message: str) -> None:
    """把记忆文件提交一次。首次调用时先初始化仓库。失败不打断记忆写入。"""
    try:
        git = get_git()
        if not git.is_initialized():
            git.init()
        else:
            git.auto_commit(message)
    except Exception as exc:  # git 出问题不该影响记忆本身
        print(f"[memory] git 提交失败（已忽略）：{exc}")


def get_git() -> GitStore:
    """返回当前用户记忆目录的 GitStore。

    每次新建（不缓存）：因为目录随当前用户变化，缓存会串到别的用户。
    GitStore 本身只是两个路径，新建代价可忽略。
    """
    return GitStore(_dir(), tracked_files=["MEMORY.md"])


def memory_log(max_entries: int = 20) -> list[dict]:
    """返回当前用户记忆的提交历史。"""
    try:
        return get_git().log(max_entries)
    except Exception as exc:
        return [{"sha": "-", "message": f"读取提交历史失败：{exc}"}]


def _next_cursor() -> int:
    """取当前用户历史日志里最后一条的 cursor + 1，没有则从 1 开始。"""
    f = _dir() / "history.jsonl"
    if not f.exists():
        return 1
    for line in reversed(f.read_text(encoding="utf-8").splitlines()):
        try:
            return int(json.loads(line)["cursor"]) + 1
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return 1


def append_history(role: str, content: str) -> None:
    """往当前用户的历史日志追加一条：cursor + 时间戳 + 角色 + 内容。"""
    if not content.strip():
        return
    entry = {
        "cursor": _next_cursor(),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "role": role,
        "content": content,
    }
    with open(_dir() / "history.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def search_history(query: str, limit: int = 20) -> str:
    """在当前用户的历史日志里搜包含 query 的记录，返回最近 limit 条（倒序）。"""
    f = _dir() / "history.jsonl"
    if not f.exists():
        return "（还没有历史记录）"
    lines = f.read_text(encoding="utf-8").splitlines()
    matches = [line for line in lines if query.lower() in line.lower()]
    if not matches:
        return "（没找到相关记录）"
    out = []
    for line in matches[-limit:]:
        entry = json.loads(line)
        out.append(f"[{entry.get('timestamp')}] {entry.get('role')}: {entry.get('content')}")
    return "\n".join(out)


# -- Dream 游标：记录「已经整理到历史日志的第几条」 -----------------------


def get_last_dream_cursor() -> int:
    """读取上次 Dream 处理到的历史游标（没做过则返回 0）。"""
    f = _dir() / ".dream_cursor"
    if f.exists():
        try:
            return int(f.read_text(encoding="utf-8").strip())
        except ValueError:
            return 0
    return 0


def set_last_dream_cursor(cursor: int) -> None:
    """把 Dream 处理到的游标写回，下次从这条之后继续整理。"""
    (_dir() / ".dream_cursor").write_text(str(cursor), encoding="utf-8")


def read_unprocessed_history(since_cursor: int, limit: int = 20) -> list[dict]:
    """返回游标大于 since_cursor 的未整理历史条目（最多 limit 条）。"""
    f = _dir() / "history.jsonl"
    if not f.exists():
        return []
    entries: list[dict] = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
            if int(entry["cursor"]) > since_cursor:
                entries.append(entry)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return entries[:limit]
