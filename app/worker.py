"""One polling loop usable from an embedded thread or a standalone process."""
import logging
import signal
import threading
from .db import init_db
from .jobs import tick

logger = logging.getLogger(__name__)


def run_loop(stop_event):
    while not stop_event.is_set():
        try:
            worked = tick()
        except Exception:
            # Do not log exception bodies: DB/provider failures can include private data.
            logger.error('Worker iteration failed; retrying after a short delay.')
            worked = False
        if not worked: stop_event.wait(1)


def start_embedded():
    stop_event = threading.Event()
    thread = threading.Thread(target=run_loop, args=(stop_event,), name='sourcing-worker', daemon=True)
    thread.start()
    return stop_event, thread


def main():
    stop_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    init_db()
    run_loop(stop_event)


if __name__ == '__main__': main()
