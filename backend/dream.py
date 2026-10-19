"""Dream：把历史对话整理进长期记忆。复刻 nanobot 的 Dream（简化版）。

nanobot 的 Dream 是个后台常驻进程，空闲时自动跑一个 agent 循环，用文件编辑工具
精准修改 SOUL.md/USER.md/MEMORY.md。这里简化成「手动触发 + 一次补全」：
调用 /api/dream 时，读未整理的历史，让模型直接输出整理后的完整 MEMORY.md，
写回去并推进游标。

效果和 nanobot 一样：把聊天里反复出现的、值得长期记住的事，提炼进 MEMORY.md。
区别只是「阿姨」变成了「你喊她才来」，以及不做精准编辑、直接整篇重写。
"""
import os

import llm
import memory

DREAM_PROMPT = """你是 Dream，记忆整理例程。把下面的对话历史合并进现有的长期记忆。

要求：
- 只输出整理后的完整 MEMORY.md 内容（Markdown），不要任何前言、解释、代码块围栏。
- 保留现有分区：User Information / Preferences / Project Context / Important Notes。
- 提炼「长期有效」的事实（名字、偏好、目标、决策），丢弃闲聊、临时报错、一次性调试细节。
- 新事实合并进对应分区；过时或被推翻的旧事实删掉。
- 如果这段历史没什么值得长期记的，就原样输出当前记忆。
"""


def _strip_fence(text: str) -> str:
    """去掉模型偶尔额外套上的 ``` 代码块围栏（外部 API 边界，顺手清理）。"""
    text = text.strip()
    if text.startswith("```"):
        first_break = text.find("\n")
        if first_break != -1:
            text = text[first_break + 1:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def consolidate(max_entries: int = 20) -> str:
    """整理未处理的历史到 MEMORY.md，返回给调用方的结果说明。"""
    if not os.getenv("DEEPSEEK_API_KEY"):
        return "（mock 模式）Dream 需要真实模型，请先在 backend/.env 配置 DEEPSEEK_API_KEY。"

    since = memory.get_last_dream_cursor()
    entries = memory.read_unprocessed_history(since, max_entries)
    if not entries:
        return "没有新的对话需要整理（历史记录都已处理完）。"

    current = memory.read() or "# Long-term Memory\n"
    history_text = "\n".join(
        f"[{e['timestamp']}] {e['role']}: {e['content']}" for e in entries
    )
    prompt = (
        f"{DREAM_PROMPT}\n\n"
        f"## 当前记忆\n\n{current}\n\n"
        f"## 未整理的对话历史\n\n{history_text}"
    )

    new_memory = _strip_fence(llm.complete(prompt))

    memory.write(new_memory, commit_message=f"dream: consolidate {len(entries)} entries")
    memory.set_last_dream_cursor(entries[-1]["cursor"])

    return f"整理完成：处理了 {len(entries)} 条对话，长期记忆已更新并提交版本。"
