import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import dream
import memory
from llm import stream_chat

router = APIRouter()


class ChatRequest(BaseModel):
    messages: list[dict]
    user_id: str | None = None


class DreamRequest(BaseModel):
    user_id: str | None = None


def _append_turn(messages: list[dict], assistant_text: list[str]) -> None:
    """把这一轮的用户消息 + 助手回复写进历史日志。"""
    last_user = messages[-1] if (messages and messages[-1].get("role") == "user") else None
    if last_user:
        memory.append_history("user", last_user.get("content", ""))
    if assistant_text:
        memory.append_history("assistant", "".join(assistant_text))


@router.post("/chat")
def chat(req: ChatRequest):
    memory.set_user(req.user_id)

    def event_stream():
        assistant_text: list[str] = []
        try:
            for event in stream_chat(req.messages):
                if event.get("delta"):
                    assistant_text.append(event["delta"])
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            _append_turn(req.messages, assistant_text)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/dream")
def trigger_dream(req: DreamRequest):
    """手动触发 Dream：把未整理的历史对话提炼进长期记忆。"""
    memory.set_user(req.user_id)
    return {"result": dream.consolidate()}


@router.get("/memory/log")
def memory_log(user_id: str | None = None):
    """查看当前用户记忆文件的提交历史（git log）。"""
    memory.set_user(user_id)
    return {"commits": memory.memory_log()}
