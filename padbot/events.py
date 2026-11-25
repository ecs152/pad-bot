"""Machine-readable progress for the Mac app: one `@ev {json}` line per event on stdout.
Event types and fields are listed in docs/events.md; add new types there when you emit them."""
import json
import sys
import time

PREFIX = "@ev "


def emit(type_, **data):
    print(PREFIX + json.dumps({"type": type_, "t": round(time.time(), 3), **data}), flush=True)
