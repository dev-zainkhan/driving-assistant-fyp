"""Wait until the server answers /api/health with the detector ready (used by start.bat).

Usage: python server/tools/wait_for_server.py [--url http://localhost:8000] [--seconds 120]
Exit code 0 when ready, 1 if it did not become ready in time.
"""
import argparse
import json
import sys
import time
import urllib.request


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--seconds", type=int, default=120)
    a = ap.parse_args()
    end = time.time() + a.seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"{a.url}/api/health", timeout=2) as r:
                health = json.loads(r.read())
            if health.get("detector") == "ready":
                print(f"server ready: device {health.get('device')}, model {health.get('model')}")
                return 0
        except Exception:
            pass
        time.sleep(1)
    print("server did not become ready; look at the server window for the error")
    return 1


if __name__ == "__main__":
    sys.exit(main())
