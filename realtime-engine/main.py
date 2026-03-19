import os
import signal
import sys
import time

import redis

from adapters.navsat import NavsatAdapter


def get_redis() -> redis.Redis:
    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "state"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        db=int(os.environ.get("REDIS_DB", "0")),
        decode_responses=True,
    )


def main() -> None:
    navsat_url = os.environ.get("NAVSAT_URL", "")
    poll_interval = int(os.environ.get("NAVSAT_POLL_INTERVAL", "15"))

    if not navsat_url:
        print("[main] NAVSAT_URL not set — idling (no telemetry source active)")
        while True:
            time.sleep(60)
        return

    r = get_redis()
    adapter = NavsatAdapter(url=navsat_url, redis_client=r, poll_interval=poll_interval)

    def shutdown(signum, frame):
        print("[main] shutting down...")
        adapter.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    print(f"[main] starting Navsat adapter (url={navsat_url}, interval={poll_interval}s)")
    adapter.start()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
