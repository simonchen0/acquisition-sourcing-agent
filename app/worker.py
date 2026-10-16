import signal
import time
from .db import init_db
from .jobs import tick

stopping = False

def stop(*_):
    global stopping
    stopping = True

def main():
    signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
    init_db()
    while not stopping:
        if not tick(): time.sleep(1)

if __name__ == '__main__': main()
