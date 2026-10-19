"""MCP 客户端加载器：复刻 nanobot 的 MCPProvider（简化版，只做 stdio 传输）。

MCP 让 agent 能「外接」别人写好的工具服务器。这里做的事：
1. 读 backend/mcp.json 配置，列出要连的 server；
2. 用 mcp SDK 连上每个 server（stdio 子进程）；
3. 把它暴露的工具包装成我们自己的 Tool，注册进全局工具表。

这样 agent 就能像调用内置工具一样，调用外部 server 的工具。

砍掉的复杂部分（nanobot 有、我们不做）：OAuth 登录、HTTP/SSE 传输、
DNS 固定防 SSRF、进度通知过滤、schema 的 $ref 归一化。
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tools import Tool, registry

MCP_CONFIG = Path(__file__).parent / "mcp.json"


def _servers() -> dict[str, dict]:
    """读取 mcp.json 里的 mcpServers 配置，格式同 Claude Desktop。"""
    if not MCP_CONFIG.exists():
        return {}
    try:
        data = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data.get("mcpServers", {})


def _params(config: dict) -> StdioServerParameters:
    """把配置里的 command/args/env 转成 SDK 需要的 StdioServerParameters。"""
    command = config.get("command", "")
    # 用当前解释器启动（保证 server 和 agent 用同一个 venv，都能 import mcp）
    if command in ("python", "python3"):
        command = sys.executable
    return StdioServerParameters(
        command=command,
        args=config.get("args", []),
        env={**os.environ, **(config.get("env") or {})},
        # 让 args 里的相对路径（如脚本路径）相对 backend 目录解析，而不是相对启动时的工作目录
        cwd=str(Path(__file__).parent),
    )


async def _list_tools(config: dict):
    """连上 server，拿到它暴露的工具列表。"""
    async with stdio_client(_params(config)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return result.tools


async def _call_tool(config: dict, name: str, arguments: dict) -> str:
    """连上 server 调一个工具，把结果里的文本内容拼成字符串返回。"""
    async with stdio_client(_params(config)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            parts = [block.text for block in result.content if getattr(block, "text", None)]
            if result.isError:
                return "错误：" + ("\n".join(parts) or "工具返回错误")
            return "\n".join(parts) or "（工具执行完毕，没有文本输出）"


def _make_caller(config: dict, name: str):
    """把一个 MCP 工具包装成「同步函数」，供 ToolRegistry 调用。"""

    def caller(**kwargs):
        # 每个调用新开一次连接（简单可靠）。agent 循环跑在线程池里，
        # 这里没有正在运行的事件循环，所以 asyncio.run 是安全的。
        return asyncio.run(_call_tool(config, name, kwargs))

    return caller


async def load_all() -> None:
    """启动时调用：把每个 server 的工具都注册进全局工具表。失败跳过不崩。"""
    for name, config in _servers().items():
        try:
            tools = await _list_tools(config)
        except Exception as exc:
            print(f"[mcp] 连接 server '{name}' 失败，已跳过：{exc}")
            continue
        for t in tools:
            tool_name = f"mcp_{name}_{t.name}"
            registry.register(
                Tool(
                    name=tool_name,
                    description=f"[来自 MCP server '{name}'] {t.description or t.name}",
                    parameters=t.inputSchema or {"type": "object", "properties": {}},
                    func=_make_caller(config, t.name),
                )
            )
        print(f"[mcp] 已加载 server '{name}'：{len(tools)} 个工具")
