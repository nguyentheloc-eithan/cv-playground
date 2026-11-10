"""Security alerts for watch-list people, and the messages sent out about them.

A watch-list match (criminal / banned person) is not just a log line:
  * it opens an ALERT that stays open until a person acknowledges it,
  * it is shown full-screen with a siren on every staff screen,
  * and it can be sent out: to security (full details) and to residents (short warning, no name, no offence).

A criminal match is only "critical" when the match is CONFIRMED (score at or above
`alerts.watchlist_confirm_score`). A weaker, merely POSSIBLE match is raised as "high" with the instruction
to verify identity first, because face recognition can be wrong and a false accusation does real harm.
"""
import base64
import json
import logging
import threading
import urllib.request
import uuid
from datetime import datetime

from . import access

log = logging.getLogger("entryguard.alerts")


def classify(cfg, person, score):
    """(level, confidence) for a watch-list match."""
    kind = access.person_type(cfg, person["person_type"])
    confirmed = score >= cfg["alerts"]["watchlist_confirm_score"]
    level = "critical" if kind.get("severity") == "critical" and confirmed else "high"
    return level, "confirmed" if confirmed else "possible"


# ------------------------------------------------------------------------------- the messages
def security_text(alert, person, camera_name, cfg):
    kind = access.person_type(cfg, person["person_type"])
    watch = person.get("watch") or {}
    lines = [f"{alert['level'].upper()} SECURITY ALERT: {kind.get('label', 'watch-list person')} detected",
             f"Person: {person['name']} ({person['code']})",
             f"Camera: {camera_name}   Time: {datetime.fromtimestamp(alert['ts']).strftime('%d %b %H:%M:%S')}",
             f"Match: {alert['confidence']} (score {alert['score']:.2f})"]
    if watch.get("reason"):
        lines.append(f"Reason on file: {watch['reason']}")
    if watch.get("instructions"):
        lines.append(f"Instructions: {watch['instructions']}")
    lines.append("Verify identity before acting. Face recognition can be wrong.")
    return "\n".join(lines)


def residents_text(alert, camera_name):
    return ("SECURITY ALERT: a person on the security watch list was detected at "
            f"{camera_name} at {datetime.fromtimestamp(alert['ts']).strftime('%H:%M')}. "
            "Do not open doors or approach them. Contact security. This is a precaution; the match can be wrong.")


# ---------------------------------------------------------------------------------- sending
def _multipart(fields, file_name, file_bytes):
    boundary = uuid.uuid4().hex
    body = b""
    for key, value in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="{file_name}"\r\n'
             "Content-Type: image/jpeg\r\n\r\n").encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def http_send(channel, payload):
    """Deliver one message. Telegram (text, or photo with caption) or a JSON webhook."""
    if channel["type"] == "telegram":
        base = f"https://api.telegram.org/bot{channel['token']}"
        if payload["photo"]:
            body, ctype = _multipart({"chat_id": channel["chat_id"], "caption": payload["text"][:1000]},
                                     "snapshot.jpg", payload["photo"])
            request = urllib.request.Request(base + "/sendPhoto", data=body, headers={"Content-Type": ctype})
        else:
            request = urllib.request.Request(
                base + "/sendMessage", data=json.dumps({"chat_id": channel["chat_id"], "text": payload["text"]}).encode(),
                headers={"Content-Type": "application/json"})
    elif channel["type"] == "webhook":
        data = {"level": payload["level"], "audience": payload["audience"], "text": payload["text"], "time": payload["time"],
                "camera": payload["camera"]}
        if payload["photo"]:
            data["snapshot_base64"] = base64.b64encode(payload["photo"]).decode()
        request = urllib.request.Request(channel["url"], data=json.dumps(data).encode(),
                                         headers={"Content-Type": "application/json"})
    else:
        raise ValueError(f"unknown channel type {channel['type']!r}")
    urllib.request.urlopen(request, timeout=10).read()


class AlertService:
    """Opens (or updates) alerts and sends the notifications, without ever blocking a camera scan."""
    def __init__(self, cfg, db, sender=http_send, background=True):
        self.cfg, self.db, self.sender, self.background = cfg, db, sender, background

    def raise_for(self, result, event_id, camera_id, snapshot, person):
        """Called by the scanner when a recognised person is on the watch list. Returns the alert."""
        level, confidence = classify(self.cfg, person, result["score"])
        alert, is_new = self.db.raise_alert(level, confidence, person["id"], event_id, camera_id, result["score"],
                                            self.cfg["alerts"]["cooldown_seconds"])
        if is_new:
            self.db.audit("system", "alert_raised", {"alert": alert["id"], "level": level, "confidence": confidence,
                                                     "person": person["code"], "camera": camera_id})
            self._notify(alert, person, camera_id, snapshot)
        return alert

    def _notify(self, alert, person, camera_id, snapshot):
        channels = self.cfg["alerts"]["channels"]
        if not channels:
            return
        camera = (self.db.get_camera(camera_id) or {}).get("name", camera_id)
        when = datetime.fromtimestamp(alert["ts"]).isoformat(timespec="seconds")

        def work():
            for channel in channels:
                audience = channel.get("audience", "security")
                payload = {"audience": audience, "level": alert["level"], "camera": camera, "time": when,
                           "photo": snapshot if channel.get("photo", True) else None,
                           "text": residents_text(alert, camera) if audience == "residents"
                           else security_text(alert, person, camera, self.cfg)}
                try:
                    self.sender(channel, payload)
                    self.db.audit("system", "alert_sent", {"alert": alert["id"], "channel": channel["type"], "audience": audience})
                except Exception as e:      # a broken channel must never stop the others
                    log.warning("alert delivery failed (%s): %s", channel["type"], e.__class__.__name__)
                    self.db.audit("system", "alert_send_failed", {"alert": alert["id"], "channel": channel["type"],
                                                                  "audience": audience, "error": e.__class__.__name__})
        if self.background:
            threading.Thread(target=work, daemon=True, name="alert-notify").start()
        else:
            work()
