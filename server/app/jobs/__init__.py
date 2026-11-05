"""长任务处理函数，按 jobs.type 登记，由 Worker 调用。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job


@dataclass(frozen=True)
class Handler:
    # 执行过程中用 services.jobs.set_stage 更新阶段和进度；出错直接抛异常
    run: Callable[[AsyncSession, Job], Awaitable[None]]
    # 最终失败、不再重试时调用，把对应的资源也标成失败；和任务状态在同一个事务里提交
    on_failed: Callable[[AsyncSession, Job], Awaitable[None]]


HANDLERS: dict[str, Handler] = {}
