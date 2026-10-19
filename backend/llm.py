import datetime
import json
import os
import time
from typing import Iterator

from dotenv import load_dotenv
from openai import OpenAI

import skills
import memory
from tools import registry as TOOLS

load_dotenv()

BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def build_system_prompt() -> str:
    """动态拼系统提示词：身份 + 长期记忆 + 常驻技能全文 + 技能摘要。

    每次请求都重新读记忆，这样模型上一次 save_memory 的内容下一次就能看到。
    """
    parts = [
        "你是 FluxAgent，一个个人 AI 助手。\n"
        "你有两类能力：\n"
        "- 工具（Tools）：可以直接调用的函数（get_current_time、run_python、exec_session、run_command、read_file、write_file、edit_file、list_dir、find_files、grep、apply_patch、web_fetch、save_memory、search_history、subagent、cron）。\n"
        "- 技能（Skills）：Markdown 说明书。遇到相关任务时，先用 read_file 读取技能正文，再照着执行。",
    ]

    mem = memory.read()
    if mem:
        parts.append(mem)

    active = skills.get_always_skills()
    if active:
        parts.append(f"# Active Skills\n\n{skills.load_skills_for_context(active)}")

    parts.append(skills.summary(exclude=set(active)))

    return "\n\n---\n\n".join(parts)


_client: OpenAI | None = None

MOCK_REPLY = """你好，我是 FluxAgent。现在是 **mock 模式**——还没接入真实的 DeepSeek key，所以这段话是「假回答」，用来测试界面。

你会看到它一个字一个字地冒出来，这就是**流式渲染**。下面顺便测试几个功能：

1. Markdown 列表（remark-gfm 支持）
2. `行内代码` 和 **加粗**
3. 一段代码块，测试语法高亮：

```python
def hello(name: str) -> str:
    # 这是一行注释
    return f"你好，{name}！"

print(hello("世界"))
```

| 功能 | 状态 |
| ---- | ---- |
| 流式渲染 | OK |
| Markdown | OK |
| 代码高亮 | OK |

把 `DEEPSEEK_API_KEY` 填进 `backend/.env` 后重启后端，这里就会变成真实的大模型回答。
"""


def _get_client() -> OpenAI:
    """懒加载：第一次真正调用时才创建客户端，并校验密钥。"""
    global _client
    if _client is None:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("缺少 DEEPSEEK_API_KEY，请在 backend/.env 里配置")
        _client = OpenAI(api_key=api_key, base_url=BASE_URL)
    return _client


def complete(prompt: str) -> str:
    """单次非流式补全，返回完整文本。供 Dream 等内部流程使用（不走工具循环）。"""
    resp = _get_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content or ""


SUBAGENT_SYSTEM = (
    "你是 FluxAgent 的一个子代理（subagent）。"
    "主代理派你独立完成一个任务。你可以调用工具。"
    "完成任务后，直接输出任务的结果本身——不要向主代理提问，也不要复述你做了哪些步骤。"
)

SUBAGENT_MAX_TURNS = 6


def run_subagent(task: str) -> str:
    """子代理：独立跑一个非流式 agent 循环，完成一个任务，返回最终文本。

    和 stream_chat 的区别：不流式、用自己的系统提示词、拿不到 subagent 工具
    （防止子代理再开子代理导致无限递归）、有轮数上限。
    """
    if not os.getenv("DEEPSEEK_API_KEY"):
        return f"（mock 模式）子代理需要真实 key 才能运行。收到任务：{task}"

    conversation = [
        {"role": "system", "content": SUBAGENT_SYSTEM},
        {"role": "user", "content": task},
    ]
    # 过滤掉 subagent 本身，防止无限嵌套
    defs = [t for t in TOOLS.get_definitions() if t["function"]["name"] != "subagent"]

    for _ in range(SUBAGENT_MAX_TURNS):
        resp = _get_client().chat.completions.create(
            model=MODEL,
            messages=conversation,
            tools=defs,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return msg.content or "（子代理没有返回内容）"

        conversation.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {}
            result = TOOLS.execute(tc.function.name, args)
            conversation.append(
                {"role": "tool", "tool_call_id": tc.id, "content": result}
            )

    return "（子代理达到最大轮数，仍没给出最终回答）"


def _stream_mock() -> Iterator[dict]:
    """没有 key 时的假流式：先演示一次工具调用，再流式输出文字。"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    yield {"tool": "get_current_time"}
    time.sleep(0.4)
    reply = f"（mock 模式）我先调用了 get_current_time 工具，现在是 {now}。\n\n" + MOCK_REPLY
    for char in reply:
        yield {"delta": char}
        time.sleep(0.01)


def stream_chat(messages: list[dict]) -> Iterator[dict]:
    """Agent 循环：让模型决定「调用工具」还是「直接回答」，直到给出最终文字。

    产出事件 dict：
    - {"delta": 文本片段}
    - {"tool": 工具名}
    - {"done": True}
    """
    if not os.getenv("DEEPSEEK_API_KEY"):
        yield from _stream_mock()
        return

    conversation = [{"role": "system", "content": build_system_prompt()}, *messages]

    while True:
        stream = _get_client().chat.completions.create(
            model=MODEL,
            messages=conversation,
            tools=TOOLS.get_definitions(),
            stream=True,
        )

        tool_calls: dict[int, dict] = {}

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield {"delta": delta.content}
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    entry = tool_calls.setdefault(
                        tc.index, {"id": "", "name": "", "arguments": ""}
                    )
                    if tc.id:
                        entry["id"] = tc.id
                    if tc.function and tc.function.name:
                        entry["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        entry["arguments"] += tc.function.arguments

        # 这一轮没有工具调用 → 已经流式输出了最终回答
        if not tool_calls:
            yield {"done": True}
            return

        # 模型要调工具：把 assistant 的 tool_calls 消息 + 工具结果补进对话，继续循环
        ordered = [tool_calls[i] for i in sorted(tool_calls)]
        conversation.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in ordered
                ],
            }
        )

        for tc in ordered:
            yield {"tool": tc["name"]}
            try:
                args = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                args = {}
            result = TOOLS.execute(tc["name"], args)
            conversation.append(
                {"role": "tool", "tool_call_id": tc["id"], "content": result}
            )
