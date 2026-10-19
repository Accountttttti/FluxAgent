"""定时任务服务：内存任务表 + 后台线程轮询触发。

复刻 nanobot 的 cron 能力（让 agent 定个闹钟、按时自己醒来干活）。砍掉的部分：
- 持久化：nanobot 用 SQLite，我们重启就丢（内存态）。
- 会话路由：nanobot 把结果送回原会话，我们写进 history.jsonl（可被 search_history /
  Dream 看到）。
- IANA 时区：我们用本地时间。
- cron 表达式只支持 5 字段 + `*` / `*/n` / 范围 `a-b` / 列表 `a,b`（不支持 `?`/`L`/`W`/年份）。

触发时的「干活」：复用了 llm.run_subagent —— 到期时像开一个子代理一样，
拿 message 当任务自主跑一遍，结果写进历史日志。
"""
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class CronJob:
    id: str
    name: str
    message: str
    kind: str                      # "every" | "at" | "cron"
    every_seconds: int | None = None
    at_epoch: float | None = None
    cron_expr: str | None = None
    delete_after_run: bool = False
    next_run: float = 0.0
    last_run: float | None = None
    last_result: str | None = None


def _parse_field(field: str, lo: int, hi: int) -> set[int]:
    """解析 cron 表达式的一个字段（分/时/日/月/周），返回允许的整数值集合。"""
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if part == "*":
            values.update(range(lo, hi + 1))
        elif "/" in part:
            base, step = part.split("/")
            step = int(step)
            start, end = (lo, hi) if base == "*" else (int(base), int(base))
            values.update(range(start, end + 1, step))
        elif "-" in part:
            a, b = part.split("-")
            values.update(range(int(a), int(b) + 1))
        else:
            values.add(int(part))
    return values


def _next_run_from_cron(expr: str, after_epoch: float) -> float | None:
    """计算 cron 表达式在 after_epoch 之后的下一次触发时间（分钟粒度）。"""
    try:
        minute, hour, dom, month, dow = expr.split()
    except ValueError:
        return None
    mins = _parse_field(minute, 0, 59)
    hours = _parse_field(hour, 0, 23)
    doms = _parse_field(dom, 1, 31)
    months = _parse_field(month, 1, 12)
    dows = _parse_field(dow, 0, 6)
    t = datetime.fromtimestamp(after_epoch).replace(second=0, microsecond=0) + timedelta(minutes=1)
    # 最多往后找 3 年（常见表达式秒出；病态表达式直接放弃）
    for _ in range(60 * 24 * 366 * 3):
        if (
            t.minute in mins
            and t.hour in hours
            and t.day in doms
            and t.month in months
            and (t.weekday() + 1) % 7 in dows
        ):
            return t.timestamp()
        t += timedelta(minutes=1)
    return None


def _run_job(message: str) -> str:
    """到期时执行：复用子代理自主跑一遍，结果写进历史日志。"""
    import memory
    from llm import run_subagent

    result = run_subagent(message)
    memory.append_history("cron", f"[定时任务] {message}\n\n结果：\n{result}")
    return result


class CronService:
    def __init__(self) -> None:
        self._jobs: dict[str, CronJob] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # -- 供工具调用 -------------------------------------------------

    def add(self, name: str | None, message: str, every_seconds: int | None,
            cron_expr: str | None, at: str | None) -> str:
        """校验并新增任务，返回结果描述。"""
        if not message.strip():
            return "错误：add 需要一个非空的 message（任务到期时要干的事）"
        count = sum(v is not None for v in (every_seconds, cron_expr, at))
        if count != 1:
            return "错误：every_seconds、cron_expr、at 三者只能且必须提供一个"

        now = time.time()
        if every_seconds is not None:
            if every_seconds <= 0:
                return "错误：every_seconds 必须是正整数（秒）"
            job = CronJob(
                id=uuid.uuid4().hex[:8], name=name or message[:30], message=message,
                kind="every", every_seconds=every_seconds, next_run=now + every_seconds,
            )
        elif at is not None:
            try:
                dt = datetime.fromisoformat(at)
            except ValueError:
                return "错误：at 格式不对，要 ISO 时间，如 2026-02-12T10:30:00"
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            at_epoch = dt.timestamp()
            if at_epoch <= now:
                return "错误：at 时间必须是未来时间"
            job = CronJob(
                id=uuid.uuid4().hex[:8], name=name or message[:30], message=message,
                kind="at", at_epoch=at_epoch, next_run=at_epoch, delete_after_run=True,
            )
        else:
            nr = _next_run_from_cron(cron_expr, now)
            if nr is None:
                return f"错误：cron 表达式 '{cron_expr}' 无法解析（要 5 字段，如 '0 9 * * *'）"
            job = CronJob(
                id=uuid.uuid4().hex[:8], name=name or message[:30], message=message,
                kind="cron", cron_expr=cron_expr, next_run=nr,
            )
        with self._lock:
            self._jobs[job.id] = job
        return f"已创建定时任务 '{job.name}'（id: {job.id}），下次触发：{self._format_time(job.next_run)}"

    def list(self) -> str:
        with self._lock:
            jobs = list(self._jobs.values())
        if not jobs:
            return "（当前没有定时任务）"
        lines = []
        for j in jobs:
            if j.kind == "every":
                timing = f"每 {j.every_seconds} 秒"
            elif j.kind == "at":
                timing = f"一次性 @ {self._format_time(j.at_epoch)}"
            else:
                timing = f"cron: {j.cron_expr}"
            line = f"- {j.name}（id: {j.id}，{timing}，下次 {self._format_time(j.next_run)}）"
            if j.last_run is not None:
                result = (j.last_result or "").replace("\n", " ")[:80]
                line += f"\n  上次运行 {self._format_time(j.last_run)}：{result}"
            lines.append(line)
        return "定时任务：\n" + "\n".join(lines)

    def remove(self, job_id: str | None) -> str:
        if not job_id:
            return "错误：remove 需要 job_id"
        with self._lock:
            job = self._jobs.pop(job_id, None)
        return f"已删除任务 {job_id}" if job else f"任务 {job_id} 不存在"

    # -- 后台调度 ---------------------------------------------------

    @staticmethod
    def _format_time(epoch: float) -> str:
        return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S")

    def start(self) -> None:
        """启动后台轮询线程（幂等）。"""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="cron-loop")
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            now = time.time()
            due: list[CronJob] = []
            with self._lock:
                for job in list(self._jobs.values()):
                    if job.next_run <= now:
                        due.append(job)
            for job in due:
                self._fire(job)
            self._stop.wait(5)

    def _fire(self, job: CronJob) -> None:
        job.last_run = time.time()
        try:
            job.last_result = _run_job(job.message)
        except Exception as exc:
            job.last_result = f"错误：{exc}"

        if job.kind == "every":
            job.next_run = time.time() + (job.every_seconds or 60)
        elif job.kind == "cron":
            nr = _next_run_from_cron(job.cron_expr or "* * * * *", time.time())
            job.next_run = nr if nr is not None else time.time() + 3600
        else:  # "at" 一次性，触发后移除
            with self._lock:
                self._jobs.pop(job.id, None)


cron_service = CronService()
