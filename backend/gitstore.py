"""记忆文件的 git 版本管理：复刻 nanobot 的 GitStore（简化版）。

nanobot 用纯 Python 的 dulwich 库做 git，避免依赖系统 git 命令。这里反过来：
直接用系统 `git` 命令（subprocess），更直观、你随时能进 memory 目录敲 `git log`
看记忆是怎么一步步演变的。语义和 nanobot 一致——每次记忆变更自动提交，可以看历史、
可以回滚。

只跟踪 MEMORY.md（nanobot 还跟踪 SOUL.md/USER.md/.dream_cursor，我们只有单文件，
就只跟踪这一个）。history.jsonl 是流水日志，不纳入版本管理。
"""
import subprocess
from pathlib import Path

GITIGNORE = "/*\n!.gitignore\n!MEMORY.md\n"


class GitStoreError(RuntimeError):
    """记忆 git 仓库操作失败时抛出。"""


class GitStore:
    """用系统 git 命令给记忆文件做版本管理。"""

    def __init__(self, workspace: Path, tracked_files: list[str]):
        self._workspace = workspace
        self._tracked_files = tracked_files

    # -- 基础 ---------------------------------------------------------------

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        """在 workspace 目录里执行一条 git 命令。"""
        return subprocess.run(
            ["git", "-C", str(self._workspace), *args],
            capture_output=True,
            text=True,
        )

    def is_initialized(self) -> bool:
        return (self._workspace / ".git").is_dir()

    # -- init ---------------------------------------------------------------

    def init(self) -> bool:
        """初始化 git 仓库并做首次提交。已初始化则返回 False。"""
        if self.is_initialized():
            return False

        self._workspace.mkdir(parents=True, exist_ok=True)

        r = self._run("init")
        if r.returncode != 0:
            raise GitStoreError(f"git init 失败：{r.stderr.strip()}")

        (self._workspace / ".gitignore").write_text(GITIGNORE, encoding="utf-8")

        # 确保被跟踪的文件存在，首次提交才有内容可提交
        for rel in self._tracked_files:
            p = self._workspace / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                p.write_text("", encoding="utf-8")

        # 提交需要一个身份，单独给这个仓库配置本地身份（不影响全局 git 配置）
        self._run("config", "user.name", "FluxAgent")
        self._run("config", "user.email", "fluxagent@local")

        self._run("add", ".gitignore", *self._tracked_files)
        r = self._run("commit", "-m", "init: memory store")
        if r.returncode != 0:
            raise GitStoreError(f"git 首次提交失败：{r.stderr.strip()}")
        return True

    # -- 日常提交 -----------------------------------------------------------

    def auto_commit(self, message: str) -> str | None:
        """把跟踪文件的变更提交一次，返回短 SHA；没有变更则返回 None。"""
        if not self.is_initialized():
            return None

        self._run("add", *self._tracked_files)

        # 检查暂存区是否有变更（--quiet：有差异返回 1，无差异返回 0）
        check = self._run("diff", "--cached", "--quiet")
        if check.returncode == 0:
            return None

        r = self._run("commit", "-m", message)
        if r.returncode != 0:
            raise GitStoreError(f"git 提交失败：{r.stderr.strip()}")

        sha = self._run("rev-parse", "--short", "HEAD")
        return sha.stdout.strip() or None

    # -- 查询 ---------------------------------------------------------------

    def log(self, max_entries: int = 20) -> list[dict]:
        """返回最近的提交列表 [{sha, message}]，按时间倒序。"""
        if not self.is_initialized():
            return []
        r = self._run("log", "--oneline", f"-{max_entries}")
        if r.returncode != 0:
            raise GitStoreError(f"git log 失败：{r.stderr.strip()}")
        entries: list[dict] = []
        for line in r.stdout.splitlines():
            sha, _, message = line.partition(" ")
            entries.append({"sha": sha, "message": message})
        return entries

    def revert(self, sha: str) -> str | None:
        """回滚某次提交（新建一条 revert 提交），返回新 SHA。"""
        if not self.is_initialized():
            return None
        r = self._run("revert", "--no-edit", sha)
        if r.returncode != 0:
            raise GitStoreError(f"git revert 失败：{r.stderr.strip()}")
        new_sha = self._run("rev-parse", "--short", "HEAD")
        return new_sha.stdout.strip() or None
