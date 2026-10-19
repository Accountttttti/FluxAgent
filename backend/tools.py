import datetime
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import memory


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
    root = Path(__file__).parent.resolve()
    target = (root / path).resolve()
    if not str(target).startswith(str(root)):
        return "错误：只允许读取项目目录内的文件"
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
        description="读取项目目录内的一个文件内容。技能（skills/<名字>/SKILL.md）可用此工具加载全文。",
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
