"""Shared Redis client factory.

Every Redis client in this codebase is built from the same three environment
variables (``REDIS_HOST``, ``REDIS_PORT``, ``REDIS_PASSWORD``) so that a
single place honors ``REDIS_PASSWORD`` — required by ``compose.prod.yml``,
which starts the ``state`` service with ``--requirepass ${REDIS_PASSWORD}``.

Deliberately dependency-light: only ``os.getenv``, no Django imports, so
non-Django contexts (standalone scripts, management commands run outside the
app) can import this module too.
"""

import os

import redis


def create_redis_client(db: int = 0, decode_responses: bool = True) -> redis.Redis:
    """Build a Redis client from REDIS_HOST/REDIS_PORT/REDIS_PASSWORD env vars.

    ``REDIS_PASSWORD`` is treated as unset when empty, so dev environments
    without Redis auth keep working unauthenticated.
    """
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "state"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=db,
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=decode_responses,
    )
