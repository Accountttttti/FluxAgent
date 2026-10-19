"""持久 Python 会话：多次调用共享变量（复刻 nanobot 的 exec_session，简化版）。

和 run_python 的区别：run_python 每次都是全新子进程、跑完就丢；
这里用一个常驻的命名空间，前一次定义的变量下一次还能用，适合多步数据处理
（比如先加载数据、再分析）。

简化点：单会话、进程内执行（code.InteractiveConsole）。代价是失去了 run_python
的子进程隔离和超时——所以别让模型写死循环。隔离性我们已有的 run_python 仍保留。
"""
import code
import contextlib
import io

_namespace: dict = {}
_console = code.InteractiveConsole(locals=_namespace)


def run(code_str: str) -> str:
    """在持久命名空间里执行一段代码，返回输出（表达式会打印结果）。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        needs_more = _console.push(code_str)
        if needs_more:
            print("（代码不完整，等待更多输入）")
    out = buf.getvalue().strip()
    return out or "（执行完毕，没有输出）"
