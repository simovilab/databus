import time
import signal
import sys


def shutdown(signum, frame):
    print("Shutting down...")
    sys.exit(0)


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)


def main():
    print("Service started")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
