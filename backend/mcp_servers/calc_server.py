"""一个 10 行的 MCP server：计算器。用来演示 MCP 的「server 端」长什么样。

MCP server 就是一个独立进程，用标准协议（这里走 stdio）暴露几个工具。
你的 agent 连上它，就能调用这里的 add / multiply 等函数，而不用自己实现。

跑法：`python mcp_servers/calc_server.py`（由 mcp_loader.py 作为子进程启动）。
"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calc")


@mcp.tool()
def add(a: float, b: float) -> float:
    """两个数相加。"""
    return a + b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """两个数相乘。"""
    return a * b


if __name__ == "__main__":
    mcp.run()  # 默认 stdio 传输，等待 client 连上来
