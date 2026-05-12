from types import SimpleNamespace

import pytest
from redis.exceptions import RedisError
from rq import Retry

from docchecker.core.config import Settings
from docchecker.services import task_queue
from docchecker.services.task_queue import BackgroundJobEnqueueError


def _sample_job(task_id: str) -> None:
    assert task_id


def test_enqueue_rq_job_uses_configured_retry_and_ttls(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeConnection:
        def __init__(self) -> None:
            self.ping_called = False

        def ping(self) -> None:
            self.ping_called = True

    class FakeQueue:
        instance = None

        def __init__(self, name, *, connection, default_timeout):
            self.name = name
            self.connection = connection
            self.default_timeout = default_timeout
            self.enqueue_kwargs = None
            FakeQueue.instance = self

        def enqueue_call(self, **kwargs):
            self.enqueue_kwargs = kwargs
            return SimpleNamespace(id="rq_job_1")

    connection = FakeConnection()
    monkeypatch.setattr(task_queue.Redis, "from_url", lambda url: connection)
    monkeypatch.setattr(task_queue, "Queue", FakeQueue)
    settings = Settings(
        task_execution_mode="rq",
        redis_url="redis://redis.example/2",
        rq_queue_name="checks",
        rq_job_timeout_seconds=123,
        rq_result_ttl_seconds=456,
        rq_failure_ttl_seconds=789,
        rq_retry_max=4,
        rq_retry_intervals_seconds=[1, 5, 30],
    )

    job_id = task_queue.enqueue_rq_job(settings, _sample_job, "task_1")

    assert job_id == "rq_job_1"
    assert connection.ping_called is True
    queue = FakeQueue.instance
    assert queue.name == "checks"
    assert queue.default_timeout == 123
    assert queue.enqueue_kwargs["func"] is _sample_job
    assert queue.enqueue_kwargs["args"] == ("task_1",)
    assert queue.enqueue_kwargs["timeout"] == 123
    assert queue.enqueue_kwargs["result_ttl"] == 456
    assert queue.enqueue_kwargs["failure_ttl"] == 789
    retry = queue.enqueue_kwargs["retry"]
    assert isinstance(retry, Retry)
    assert retry.max == 4
    assert retry.intervals == [1, 5, 30]


def test_enqueue_rq_job_exposes_redis_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_from_url(url: str):
        raise RedisError("redis unavailable")

    monkeypatch.setattr(task_queue.Redis, "from_url", fail_from_url)
    settings = Settings(task_execution_mode="rq")

    with pytest.raises(BackgroundJobEnqueueError, match="无法连接 Redis"):
        task_queue.enqueue_rq_job(settings, _sample_job, "task_1")
