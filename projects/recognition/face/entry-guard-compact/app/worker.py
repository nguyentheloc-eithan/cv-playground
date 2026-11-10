"""Live IP camera workers: read an RTSP stream on the server, scan it, and share the result.

One worker per camera, started when somebody looks at the camera and stopped about 20 seconds after
the last viewer leaves. Each worker uses two threads:

    reader  : reads the stream as fast as it comes and keeps ONLY the newest picture
              (so a slow face scan never makes the view lag behind)
    worker  : a few times a second, scans the newest picture, draws the boxes,
              and keeps the finished JPEG for the browser

If the stream drops, the worker reconnects by itself (waiting 1, 2, 4, then 8 seconds).
"""
import threading
import time
from collections import deque

import cv2
import numpy as np

from . import cameras

IDLE_SECONDS = 20          # stop when nobody has looked for this long
COLORS = {"resident": (128, 222, 74), "uncertain": (36, 191, 251), "unknown": (94, 107, 255)}  # BGR


def placeholder(text, width=800, height=450):
    """A dark picture with a message, shown while connecting."""
    image = np.full((height, width, 3), 14, np.uint8)
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
    cv2.putText(image, text, ((width - w) // 2, (height + h) // 2), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (200, 205, 215), 2, cv2.LINE_AA)
    return cv2.imencode(".jpg", image)[1].tobytes()


def draw_results(image, results):
    """Corner brackets and a name label for each face (same look as the browser view)."""
    for r in results:
        if not r.get("bbox"):
            continue
        x, y, w, h = (int(v) for v in r["bbox"])
        color = COLORS.get(r["decision"], (255, 255, 255))
        length = max(int(min(w, h) * 0.22), 6)
        for px, py, dx, dy in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
            cv2.line(image, (px, py), (px + dx * length, py), color, 3, cv2.LINE_AA)
            cv2.line(image, (px, py), (px, py + dy * length), color, 3, cv2.LINE_AA)
        label = r.get("person") or r["decision"]
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(image, (x, y + h + 6), (x + tw + 12, y + h + 10 + th + 6), color, -1)
        cv2.putText(image, label, (x + 6, y + h + 10 + th), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (10, 20, 10), 2, cv2.LINE_AA)
    return image


class CameraWorker:
    def __init__(self, cam, scanner, cfg, opener=cameras.open_capture):
        self.cam, self.scanner, self.opener = cam, scanner, opener
        self.max_width = cfg["scan"]["max_width"]
        self.process_interval = 1.0 / min(float(cam["fps"]), 6.0)   # face scans per second
        self.state, self.error = "connecting", ""
        self.fps, self.size = 0.0, None
        self.jpeg = placeholder("Connecting to camera...")
        self.results = []
        self.events = deque(maxlen=100)       # recent logged recognitions, each with a "seq" number
        self.seq = 0
        self.last_touch = time.time()
        self._stop = threading.Event()
        self._frame, self._frame_time, self._reader_done = None, 0.0, False
        self._stop_reader = False
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"camera-{cam['id']}")

    # ---- used by the web server
    def start(self):
        self._thread.start()
        return self

    def touch(self):
        self.last_touch = time.time()

    def alive(self):
        return self._thread.is_alive() and not self._stop.is_set()

    def stop(self):
        self._stop.set()

    def status(self, since=0):
        return {"state": self.state, "error": self.error, "fps": round(self.fps, 1),
                "size": self.size, "results": self.results, "seq": self.seq,
                "events": [e for e in self.events if e["seq"] > since]}

    # ---- internals
    def _idle(self):
        return time.time() - self.last_touch > IDLE_SECONDS

    def _run(self):
        backoff = 1
        while not self._stop.is_set() and not self._idle():
            cap = self.opener(self.cam)
            if not cap.isOpened():
                cap.release()
                self._set_state("reconnecting", "Cannot connect. Check address, login and path.")
                self._wait(backoff)
                backoff = min(backoff * 2, 8)
                continue
            backoff = 1
            self._set_state("live", "")
            self._reader_done, self._frame, self._stop_reader = False, None, False
            reader = threading.Thread(target=self._read, args=(cap,), daemon=True)
            reader.start()
            self._process()
            self._stop_reader = True
            reader.join(timeout=3)
            cap.release()
            if not self._stop.is_set() and not self._idle():
                self._set_state("reconnecting", "Stream interrupted.")
                self._wait(1)
        self._set_state("stopped", "")

    def _set_state(self, state, error):
        self.state, self.error = state, error
        if state != "live":
            self.results, self.fps = [], 0.0
            if state == "reconnecting":
                self.jpeg = placeholder("Reconnecting...")

    def _wait(self, seconds):
        end = time.time() + seconds
        while time.time() < end and not self._stop.is_set() and not self._idle():
            time.sleep(0.1)

    def _read(self, cap):
        while not self._stop.is_set() and not self._stop_reader:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            self._frame, self._frame_time = frame, time.time()
        self._reader_done = True

    def _process(self):
        """Scan the newest picture a few times a second until the stream ends."""
        last_time, counted, window = 0.0, 0, time.time()
        while not self._stop.is_set() and not self._idle():
            if self._reader_done or (self._frame_time and time.time() - self._frame_time > 5):
                return                                            # stream ended or went silent
            frame, taken = self._frame, self._frame_time
            if frame is None or taken == last_time:
                time.sleep(0.02)
                continue
            last_time = taken
            started = time.time()
            height, width = frame.shape[:2]
            if width > self.max_width:                           # shrink for speed
                frame = cv2.resize(frame, (self.max_width, int(height * self.max_width / width)))
            self.size = [width, height]
            results = self.scanner.scan(frame.copy(), self.cam["id"])
            for r in results:
                if r.get("event_id"):
                    self.seq += 1
                    self.events.append({**r, "seq": self.seq, "at": time.time()})
            self.results = results
            self.jpeg = cv2.imencode(".jpg", draw_results(frame, results),
                                     [cv2.IMWRITE_JPEG_QUALITY, 75])[1].tobytes()
            counted += 1
            if time.time() - window >= 2:
                self.fps, counted, window = counted / (time.time() - window), 0, time.time()
            time.sleep(max(0.0, self.process_interval - (time.time() - started)))


class WorkerManager:
    """Keeps one running worker per camera."""
    def __init__(self, db, scanner, cfg, opener=cameras.open_capture):
        self.db, self.scanner, self.cfg, self.opener = db, scanner, cfg, opener
        self.workers = {}
        self.lock = threading.Lock()

    def ensure(self, camera_id):
        """The running worker for a camera (started if needed). None if it is not an enabled IP camera."""
        cam = self.db.get_camera(camera_id)
        if not cam or cam["kind"] != "rtsp" or not cam["enabled"]:
            return None
        with self.lock:
            worker = self.workers.get(camera_id)
            if not worker or not worker.alive():
                worker = self.workers[camera_id] = CameraWorker(
                    cam, self.scanner, self.cfg, self.opener).start()
            worker.touch()
            return worker

    def stop(self, camera_id):
        """Stop a camera's worker (after it was edited, disabled or deleted)."""
        with self.lock:
            worker = self.workers.pop(camera_id, None)
        if worker:
            worker.stop()

    def stop_all(self):
        for camera_id in list(self.workers):
            self.stop(camera_id)
