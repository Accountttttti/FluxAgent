import datetime
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import cron
import exec_session
import fstools
import memory
import webtools


class Tool:
    """复刻 nanobot 的 Tool 基类（简化版）：名字 + 说明 + 参数 schema + 执行函数。"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        func: Callable[..., str],
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self._func = func

    def to_schema(self) -> dict:
        """生成 OpenAI function calling 需要的 schema。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(self, **kwargs: Any) -> str:
        return self._func(**kwargs)


class ToolRegistry:
    """工具注册表：登记工具、生成 schema、执行工具。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_definitions(self) -> list[dict]:
        return [tool.to_schema() for tool in self._tools.values()]

    def execute(self, name: str, args: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"错误：工具 '{name}' 不存在"
        try:
            return tool.execute(**args)
        except Exception as exc:
            return f"错误：执行工具 {name} 失败：{exc}"


def _get_current_time() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S（%A）")


def _run_python(code: str) -> str:
    """在隔离子进程里执行一段 Python 代码，10 秒超时，返回输出。"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return output.strip() or "（代码执行完毕，没有输出）"
    except subprocess.TimeoutExpired:
        return "错误：代码执行超时（10 秒）"


def _run_command(command: str) -> str:
    """执行一条 shell 命令，返回输出。供技能（如 weather 的 curl）使用。"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return output.strip() or "（命令执行完毕，没有输出）"
    except subprocess.TimeoutExpired:
        return "错误：命令执行超时（30 秒）"


def _read_file(path: str) -> str:
    """读取项目目录内的一个文件（用于模型加载技能 SKILL.md 全文）。"""
    try:
        target = fstools.resolve(path)
    except ValueError as exc:
        return f"错误：{exc}"
    try:
        return target.read_text(encoding="utf-8")
    except Exception as exc:
        return f"错误：读取文件失败：{exc}"


def _save_memory(content: str) -> str:
    """把重要信息写进长期记忆（覆盖 memory/MEMORY.md）。"""
    return memory.write(content)


def _search_history(query: str) -> str:
    """搜索历史对话记录（memory/history.jsonl），回忆过去聊过的内容。"""
    return memory.search_history(query)


def _subagent(task: str) -> str:
    """开一个子代理独立完成一个任务。延迟导入 llm 避免循环依赖。"""
    from llm import run_subagent

    return run_subagent(task)


def _cron(
    action: str,
    name: str | None = None,
    message: str = "",
    every_seconds: int | None = None,
    cron_expr: str | None = None,
    at: str | None = None,
    job_id: str | None = None,
) -> str:
    """定时任务：add / list / remove。"""
    if action == "add":
        return cron.cron_service.add(name, message, every_seconds, cron_expr, at)
    if action == "list":
        return cron.cron_service.list()
    if action == "remove":
        return cron.cron_service.remove(job_id)
    return f"错误：未知的 cron 动作 '{action}'"


registry = ToolRegistry()

registry.register(
    Tool(
        name="get_current_time",
        description="获取当前日期和时间。当用户问「现在几点」「今天几号」时调用。",
        parameters={"type": "object", "properties": {}},
        func=_get_current_time,
    )
)

registry.register(
    Tool(
        name="run_python",
        description="执行一段 Python 代码并返回输出，用于计算、数据处理等。代码在隔离子进程运行，10 秒超时。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "要执行的 Python 代码"},
            },
            "required": ["code"],
        },
        func=_run_python,
    )
)

registry.register(
    Tool(
        name="run_command",
        description="执行一条 shell 命令并返回输出，用于运行 curl、查看文件等。30 秒超时。",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的 shell 命令"},
            },
            "required": ["command"],
        },
        func=_run_command,
    )
)

registry.register(
    Tool(
        name="read_file",
        description="读取项目目录内的一个文件内容。技能（backend/skills/<名字>/SKILL.md）可用此工具加载全文。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对项目根目录的文件路径"},
            },
            "required": ["path"],
        },
        func=_read_file,
    )
)

registry.register(
    Tool(
        name="save_memory",
        description="把需要长期记住的重要信息写入记忆文件（覆盖 memory/MEMORY.md）。当用户告诉你他的偏好、背景、项目信息等「以后也要记住」的事时调用。",
        parameters={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "要保存的完整记忆内容（Markdown 格式）"},
            },
            "required": ["content"],
        },
        func=_save_memory,
    )
)

registry.register(
    Tool(
        name="search_history",
        description="搜索历史对话记录（memory/history.jsonl）。当需要回忆过去聊过的内容、用户之前说过的话时调用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "要搜索的关键词或短语"},
            },
            "required": ["query"],
        },
        func=_search_history,
    )
)

registry.register(
    Tool(
        name="subagent",
        description="开一个子代理（subagent）独立完成一个任务并返回结果。用于把复杂、耗时、能独立完成的子任务委托出去（如「调研某个主题」「写一段代码」「查资料汇总」），避免占用主对话上下文。子代理有自己的上下文和工具，完成后返回任务结果文本。",
        parameters={
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "要交给子代理完成的完整任务描述，要自包含、明确"},
            },
            "required": ["task"],
        },
        func=_subagent,
    )
)

registry.register(
    Tool(
        name="cron",
        description="定时任务：让 agent 在指定时间自动醒来干活。动作：add（新增）/ list（列出）/ remove（删除）。add 时 message 是「到期要干什么」，并需在 every_seconds（每 N 秒）、cron_expr（如 '0 9 * * *' 每天早上 9 点）、at（一次性 ISO 时间）三者中选一个。",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "list", "remove"], "description": "要执行的动作"},
                "name": {"type": "string", "description": "任务名字（可选，省略则用 message 前 30 字）"},
                "message": {"type": "string", "description": "add 时必填：任务到期时要执行的指令"},
                "every_seconds": {"type": "integer", "description": "每隔多少秒执行一次（周期性）"},
                "cron_expr": {"type": "string", "description": "cron 表达式，5 字段，如 '0 9 * * *'"},
                "at": {"type": "string", "description": "一次性执行时间，ISO 格式，如 '2026-10-20T09:00:00'"},
                "job_id": {"type": "string", "description": "remove 时必填：要删除的任务 id（用 list 查）"},
            },
            "required": ["action"],
        },
        func=_cron,
    )
)

registry.register(
    Tool(
        name="write_file",
        description="写一个文件（新建或覆盖），自动创建父目录。路径相对项目根目录。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对项目根目录的文件路径"},
                "content": {"type": "string", "description": "要写入的完整文件内容"},
            },
            "required": ["path", "content"],
        },
        func=fstools.write_file,
    )
)

registry.register(
    Tool(
        name="edit_file",
        description="把文件里唯一的一处 old_text 精确替换成 new_text。old_text 必须能在文件里唯一匹配。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对项目根目录的文件路径"},
                "old_text": {"type": "string", "description": "要被替换的原文（需唯一）"},
                "new_text": {"type": "string", "description": "替换后的新文本"},
            },
            "required": ["path", "old_text", "new_text"],
        },
        func=fstools.edit_file,
    )
)

registry.register(
    Tool(
        name="list_dir",
        description="列出一个目录里的文件和子目录（目录名带 / 后缀）。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对项目根目录的路径，默认 '.'"},
            },
        },
        func=fstools.list_dir,
    )
)

registry.register(
    Tool(
        name="find_files",
        description="按文件名片段找文件（大小写不敏感），返回相对路径列表。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "文件名要包含的片段"},
                "path": {"type": "string", "description": "搜索起点目录，默认 '.'"},
            },
            "required": ["query"],
        },
        func=fstools.find_files,
    )
)

registry.register(
    Tool(
        name="grep",
        description="在文件内容里搜正则表达式，返回「文件:行号: 内容」的匹配列表。",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "正则表达式"},
                "path": {"type": "string", "description": "搜索起点目录，默认 '.'"},
                "case_insensitive": {"type": "boolean", "description": "是否忽略大小写，默认 false"},
            },
            "required": ["pattern"],
        },
        func=fstools.grep,
    )
)

registry.register(
    Tool(
        name="apply_patch",
        description="按顺序应用一组结构化文件编辑（支持多文件）。每条 edit：path + action（replace=替换唯一一处 old_text；add=新建或追加 new_text）+ 对应文本。适合一次改多处/多文件。",
        parameters={
            "type": "object",
            "properties": {
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "文件路径"},
                            "action": {"type": "string", "enum": ["replace", "add"]},
                            "old_text": {"type": "string", "description": "replace 时：要被替换的原文"},
                            "new_text": {"type": "string", "description": "replace 时替换后的文本；add 时要追加的内容"},
                        },
                        "required": ["path", "action"],
                    },
                    "description": "要应用的文件编辑列表",
                },
                "dry_run": {"type": "boolean", "description": "只校验并描述改动，不真正写文件，默认 false"},
            },
            "required": ["edits"],
        },
        func=fstools.apply_patch,
    )
)

registry.register(
    Tool(
        name="web_fetch",
        description="读取一个网址并抽出可读文本（标题 + 正文）。用于上网查资料、读文章。只接受 http/https 链接。",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要抓取的网址（http/https）"},
            },
            "required": ["url"],
        },
        func=webtools.web_fetch,
    )
)

registry.register(
    Tool(
        name="exec_session",
        description="在持久 Python 会话里执行代码，变量在多次调用之间保留。适合多步数据处理（先加载数据、再分析）。注意：进程内执行、无超时，别写死循环。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "要执行的 Python 代码"},
            },
            "required": ["code"],
        },
        func=exec_session.run,
    )
)
