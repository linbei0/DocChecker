from collections.abc import Callable
from os import name as os_name
from threading import Timer
from typing import Any

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, Retry, SimpleWorker, Worker, get_current_job

from docchecker.core.config import Settings, get_settings


class BackgroundJobEnqueueError(RuntimeError):
    """后台任务入队失败。"""


def start_background_job(
    settings: Settings,
    function: Callable[..., Any],
    *args: Any,
) -> str | None:
    if settings.task_execution_mode == "inline":
        _start_inline_job(function, *args)
        return None
    return enqueue_rq_job(settings, function, *args)


def enqueue_rq_job(
    settings: Settings,
    function: Callable[..., Any],
    *args: Any,
) -> str:
    try:
        connection = _redis_connection(settings)
        queue = Queue(
            settings.rq_queue_name,
            connection=connection,
            default_timeout=settings.rq_job_timeout_seconds,
        )
        job = queue.enqueue_call(
            func=function,
            args=args,
            timeout=settings.rq_job_timeout_seconds,
            result_ttl=settings.rq_result_ttl_seconds,
            failure_ttl=settings.rq_failure_ttl_seconds,
            retry=_rq_retry(settings),
            description=f"{function.__module__}.{function.__name__}{args!r}",
        )
    except RedisError as exc:
        raise BackgroundJobEnqueueError(f"无法连接 Redis 任务队列：{exc}") from exc
    except Exception as exc:
        raise BackgroundJobEnqueueError(f"RQ 任务入队失败：{exc}") from exc
    return job.id


def current_rq_job_should_retry() -> bool:
    job = get_current_job()
    return bool(job and job.should_retry)


def current_rq_job_is_active() -> bool:
    return get_current_job() is not None


def run_worker() -> None:
    settings = get_settings()
    worker = create_worker(settings)
    worker.work(with_scheduler=True)


def create_worker(settings: Settings) -> Worker:
    connection = _redis_connection(settings)
    queue = Queue(
        settings.rq_queue_name,
        connection=connection,
        default_timeout=settings.rq_job_timeout_seconds,
    )
    # Windows 没有 fork，使用 RQ SimpleWorker 保持独立 worker 进程可启动。
    worker_type = SimpleWorker if os_name == "nt" else Worker
    return worker_type(
        [queue],
        connection=connection,
        default_result_ttl=settings.rq_result_ttl_seconds,
    )


def _start_inline_job(function: Callable[..., Any], *args: Any) -> None:
    # 先让 HTTP 响应写出，再启动 CPU 密集的文档解析，避免新线程抢占 GIL 拖慢首包。
    worker = Timer(0.1, function, args=args)
    worker.daemon = True
    worker.start()


def _redis_connection(settings: Settings) -> Redis:
    connection = Redis.from_url(settings.redis_url)
    connection.ping()
    return connection


def _rq_retry(settings: Settings) -> Retry | None:
    if settings.rq_retry_max == 0:
        return None
    return Retry(max=settings.rq_retry_max, interval=settings.rq_retry_intervals_seconds)
