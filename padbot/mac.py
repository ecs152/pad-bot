"""iPhone Mirroring window: find it, capture it, map image pixels to screen points, send mouse input.

Input is dry-run unless `live=True`, which only the CLI's --live flag sets.
"""
import os
import subprocess
import tempfile
import time

import cv2

APP = "iPhone Mirroring"


class Stop(Exception):
    """Abort the bot: kill switch, unsafe screen, missing permission."""


def find_window(retry=True):
    """Returns (window_id, (x, y, w, h) in global points).
    Stage Manager shrinks the window to a thumbnail when another app is in front: bring it back once."""
    import Quartz
    # All windows, not just on-screen ones: the mirror window can sit behind others or on another Space.
    infos = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID)
    for w in infos or []:
        if w.get("kCGWindowOwnerName") == APP and w.get("kCGWindowName") == APP and w.get("kCGWindowLayer") == 0:
            b = w["kCGWindowBounds"]
            if b["Height"] > 200:
                return w["kCGWindowNumber"], (b["X"], b["Y"], b["Width"], b["Height"])
    if retry:
        subprocess.run(["osascript", "-e", f'tell application "{APP}" to activate'], check=False)
        time.sleep(1.5)
        return find_window(retry=False)
    if not Quartz.CGPreflightScreenCaptureAccess():  # without it macOS hides window titles, so the match above fails
        raise Stop("Screen Recording permission is missing for PAD Bot (or the terminal running the bot). "
                   "Turn it on in System Settings > Privacy & Security > Screen & System Audio Recording.")
    raise Stop(f"{APP} window not found. Open {APP} and keep the window visible.")


def accessibility_ok():
    """True if this process may post mouse events. Without it macOS drops them silently."""
    import ctypes
    ax = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
    ax.AXIsProcessTrusted.restype = ctypes.c_bool
    return ax.AXIsProcessTrusted()


def capture():
    """Returns (BGR image, bounds). No window shadow (-o)."""
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        for attempt in range(5):  # the window can vanish for a moment (moved, Stage Manager, reconnect)
            wid, bounds = find_window()
            if subprocess.run(["screencapture", "-x", "-o", f"-l{wid}", path]).returncode == 0:
                break
            time.sleep(1)
        else:
            raise Stop(f"Couldn't capture the {APP} window for 5 seconds.")
        img = cv2.imread(path)
    finally:
        os.unlink(path)
    if img is None or img.size == 0:
        raise Stop("Screen capture failed. Grant Screen Recording permission (see README).")
    sx, sy = img.shape[1] / bounds[2], img.shape[0] / bounds[3]
    if abs(sx - sy) > 0.05:
        raise Stop(f"Capture {img.shape[1]}x{img.shape[0]} doesn't match window {bounds[2]}x{bounds[3]}")
    if img.std() < 3 and not __import__("Quartz").CGPreflightScreenCaptureAccess():
        raise Stop("Capture is blank and Screen Recording permission is off for PAD Bot. Turn it on in System "
                   "Settings > Privacy & Security > Screen & System Audio Recording.")
    # With the permission on, a blank frame is a loading screen: the caller sees an unknown screen and waits.
    return img, bounds


def to_point(px, py, img_w, bounds):
    """Image pixel -> global screen point. Scale comes from image width / window width (Retina = 2)."""
    x, y, w, _ = bounds
    s = img_w / w
    return x + px / s, y + py / s


def to_pixel(gx, gy, img_w, bounds):
    x, y, w, _ = bounds
    s = img_w / w
    return (gx - x) * s, (gy - y) * s


class Mouse:
    def __init__(self, live=False):
        self.live = live
        if live and not accessibility_ok():
            raise Stop("Accessibility permission is missing for PAD Bot (or the terminal running the bot), so taps "
                       "would do nothing. Turn it on in System Settings > Privacy & Security > Accessibility.")

    def _check_kill(self):
        if not self.live:
            return
        import Quartz
        p = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        if p.x < 5 and p.y < 5:
            raise Stop("Kill switch: mouse moved to the top-left corner.")

    def _post(self, kind, x, y):
        import Quartz
        e = Quartz.CGEventCreateMouseEvent(None, kind, (x, y), Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)

    def focus(self):
        if self.live:
            subprocess.run(["osascript", "-e", f'tell application "{APP}" to activate'], check=False)
            time.sleep(0.3)

    def tap(self, x, y):
        print(f"  tap ({x:.0f},{y:.0f})" + ("" if self.live else "  [dry-run]"))
        if not self.live:
            return
        import Quartz
        self._check_kill()
        self._post(Quartz.kCGEventMouseMoved, x, y)
        time.sleep(0.05)
        self._post(Quartz.kCGEventLeftMouseDown, x, y)
        time.sleep(0.08)
        self._post(Quartz.kCGEventLeftMouseUp, x, y)

    def drag(self, points, step_s=0.12, substeps=6):
        """points: global screen points of the cell centres along the route."""
        print(f"  drag {len(points) - 1} steps" + ("" if self.live else "  [dry-run]"))
        if not self.live:
            return
        import Quartz
        self._check_kill()
        (x0, y0) = points[0]
        self._post(Quartz.kCGEventMouseMoved, x0, y0)
        time.sleep(0.05)
        self._post(Quartz.kCGEventLeftMouseDown, x0, y0)
        time.sleep(0.15)
        try:
            for (ax, ay), (bx, by) in zip(points, points[1:]):
                for i in range(1, substeps + 1):
                    t = i / substeps
                    self._post(Quartz.kCGEventLeftMouseDragged, ax + (bx - ax) * t, ay + (by - ay) * t)
                    time.sleep(step_s / substeps)
        finally:
            x1, y1 = points[-1]
            self._post(Quartz.kCGEventLeftMouseUp, x1, y1)


def notify(msg):
    print("STOP:", msg)
    subprocess.run(["osascript", "-e", "on run argv", "-e",
                    'display notification (item 1 of argv) with title "pad-bot"', "-e", "end run", msg], check=False)
