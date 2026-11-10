"""IP camera helpers: check the form, build the RTSP address, test a connection.

An IP camera is described by simple fields (host, port, path, username, password) instead of one
long URL, so a person can fill a form without knowing URL syntax. The password is never sent back
to the browser (see `public`).
"""
import base64
import os
import re
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import cv2

from .recognize import RegisterError

DIRECTIONS = ("in", "out", "both")
TRANSPORTS = ("tcp", "udp")
_open_lock = threading.Lock()


def clean(data, partial=False):
    """Validate form data and return only known fields, tidied. `partial` = an edit (fields optional)."""
    out = {}

    def need(key, label):
        if not partial and not str(data.get(key, "")).strip():
            raise RegisterError("MISSING_FIELD", f"{label} is required", key)

    need("name", "Name")
    need("host", "Address")
    if "name" in data:
        out["name"] = str(data["name"]).strip()[:80]
        if not out["name"]:
            raise RegisterError("MISSING_FIELD", "Name is required", "name")
    if "location" in data:
        out["location"] = str(data["location"]).strip()[:120]
    if "host" in data:
        host = str(data["host"]).strip()
        host = re.sub(r"^rtsp://", "", host, flags=re.I).split("/")[0].split("@")[-1]
        if ":" in host and host.count(":") == 1:        # "192.168.1.210:554" typed in the address box
            host, _, port = host.partition(":")
            data = {**data, "port": data.get("port") or port}
        if not re.fullmatch(r"[A-Za-z0-9.\-]{1,253}", host):
            raise RegisterError("BAD_HOST", "Address must be an IP or a host name, for example 192.168.1.210", "host")
        out["host"] = host
    if "port" in data and str(data["port"]).strip() != "":
        try:
            port = int(data["port"])
        except (TypeError, ValueError):
            raise RegisterError("BAD_PORT", "Port must be a number", "port")
        if not 1 <= port <= 65535:
            raise RegisterError("BAD_PORT", "Port must be between 1 and 65535", "port")
        out["port"] = port
    if "path" in data:
        path = str(data["path"]).strip()
        out["path"] = ("/" + path.lstrip("/")) if path else ""
    for key in ("username", "password"):
        if key in data:
            out[key] = str(data[key])
    if "direction" in data:
        if data["direction"] not in DIRECTIONS:
            raise RegisterError("BAD_DIRECTION", "Direction must be in, out or both", "direction")
        out["direction"] = data["direction"]
    if "transport" in data:
        if data["transport"] not in TRANSPORTS:
            raise RegisterError("BAD_TRANSPORT", "Transport must be tcp or udp", "transport")
        out["transport"] = data["transport"]
    if "fps" in data:
        try:
            fps = float(data["fps"])
        except (TypeError, ValueError):
            raise RegisterError("BAD_FPS", "Frames per second must be a number", "fps")
        if not 1 <= fps <= 30:
            raise RegisterError("BAD_FPS", "Frames per second must be between 1 and 30", "fps")
        out["fps"] = fps
    if "enabled" in data:
        out["enabled"] = 1 if data["enabled"] else 0
    return out


def rtsp_url(cam, hide_password=False):
    """rtsp://user:password@host:port/path  (user and password are URL-encoded)."""
    auth = ""
    if cam.get("username"):
        password = "***" if hide_password else quote(cam.get("password", ""), safe="")
        auth = f"{quote(cam['username'], safe='')}:{password}@" if cam.get("password") else \
               f"{quote(cam['username'], safe='')}@"
    return f"rtsp://{auth}{cam['host']}:{cam['port']}{cam.get('path', '')}"


def public(cam):
    """What the browser may see: everything except the password."""
    shown = {k: v for k, v in cam.items() if k != "password"}
    shown["has_password"] = bool(cam.get("password"))
    shown["url"] = rtsp_url(cam, hide_password=True) if cam["kind"] == "rtsp" else None
    return shown


def open_capture(cam, timeout_ms=5000, serialize=True):
    """Open an RTSP stream with OpenCV. Returns a cv2.VideoCapture (check .isOpened()).

    The transport (tcp/udp) is a process-wide OpenCV setting, so normally only one stream is opened
    at a time (`serialize`). Path discovery opens many streams at once with the same transport and
    turns this off."""
    os_options = f"rtsp_transport;{cam['transport']}"
    params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms, cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms]
    if serialize:
        with _open_lock:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = os_options
            cap = cv2.VideoCapture(rtsp_url(cam), cv2.CAP_FFMPEG, params)
    else:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = os_options
        cap = cv2.VideoCapture(rtsp_url(cam), cv2.CAP_FFMPEG, params)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # keep only the newest picture, so the view is not delayed
    return cap


def tcp_reachable(host, port, timeout=2.0):
    """Can we open a network connection to host:port at all? (Quick check before slower tests.)"""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def expand_path(path, channel=1):
    """Fill the channel placeholders of a catalog path: {ch} -> 1, {ch2} -> 01."""
    return path.replace("{ch2}", f"{int(channel):02d}").replace("{ch}", str(int(channel)))


def candidate_paths(presets, templates, channel=1):
    """Every distinct stream path we know of (catalog first, then user templates)."""
    seen, out = set(), []
    paths = [stream["path"] for brand in presets for stream in brand.get("streams", [])]
    paths += [t["path"] for t in templates]
    for path in paths:
        path = expand_path(path, channel)
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out


def discover_paths(cam, candidates, opener=None, reachable=tcp_reachable, workers=6, budget=45):
    """Try many stream paths on one camera and report which ones give a picture.

    Returns {"reachable": bool, "tried": n, "found": [{"path", "width", "height"}...]}.
    Several tries run in parallel; the whole search stops after `budget` seconds."""
    if not reachable(cam["host"], cam["port"]):
        return {"reachable": False, "tried": 0, "found": []}
    opener = opener or (lambda c: open_capture(c, timeout_ms=3000, serialize=False))

    def try_path(path):
        attempt = {**cam, "path": path}
        cap = opener(attempt)
        try:
            if not cap.isOpened():
                return None
            ok, frame = cap.read()
            if not ok or frame is None:
                return None
            return {"path": path, "width": int(frame.shape[1]), "height": int(frame.shape[0])}
        finally:
            cap.release()

    found, order = [], {path: i for i, path in enumerate(candidates)}
    pool = ThreadPoolExecutor(max_workers=workers)
    futures = [pool.submit(try_path, path) for path in candidates]
    try:
        for future in as_completed(futures, timeout=budget):
            hit = future.result()
            if hit:
                found.append(hit)
    except Exception:       # timed out: report what we have
        pass
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    found.sort(key=lambda h: order[h["path"]])
    return {"reachable": True, "tried": len(candidates), "found": found}


def test_connection(cam, timeout=10, opener=None):
    """Try to open the stream and read one picture. Never raises; never includes the password."""
    result = {"ok": False, "message": "", "width": None, "height": None, "latency_ms": None,
              "preview": None}

    def work():
        started = time.time()
        cap = (opener or open_capture)(cam)
        try:
            if not cap.isOpened():
                result["message"] = ("Cannot connect. Check the address, port, user name and password, "
                                     "and that the camera is on the same network.")
                return
            ok, frame = cap.read()
            if not ok or frame is None:
                result["message"] = "Connected but no picture arrived. Check the stream path."
                return
            height, width = frame.shape[:2]
            small = cv2.resize(frame, (480, int(480 * height / width))) if width > 480 else frame
            _, buffer = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])
            result.update(ok=True, message="Connection works", width=width, height=height,
                          latency_ms=int((time.time() - started) * 1000),
                          preview="data:image/jpeg;base64," + base64.b64encode(buffer).decode())
        finally:
            cap.release()

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        result["message"] = "Timed out. The camera did not answer."
    return result
