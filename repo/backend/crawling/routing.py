"""
crawling/routing.py — Consistent-hash shard routing for crawl tasks.

Crawl tasks for a given source always land on the same worker shard, which
means per-source rate-limiting and quota state stays local to one process —
no cross-worker contention on SourceQuota rows.

NUM_SHARDS is intentionally small (4).  Raising it requires restarting
workers that subscribe to the new queue names.
"""

NUM_SHARDS = 4


def crawl_queue_for_source(source_id: int) -> str:
    """Return the Celery queue name for the given source ID.

    >>> crawl_queue_for_source(1)
    'crawl.1'
    >>> crawl_queue_for_source(5)
    'crawl.1'
    """
    shard = source_id % NUM_SHARDS
    return f"crawl.{shard}"


# All shard queue names — used by the Celery worker --queues flag.
CRAWL_SHARD_QUEUES: list[str] = [f"crawl.{i}" for i in range(NUM_SHARDS)]
