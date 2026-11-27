"""Outbound alert delivery on a background thread so a slow Telegram never blocks the device API."""
import hashlib
import hmac
import json
import logging
import queue
import threading

import httpx

from . import settings

log = logging.getLogger("solavis.notify")
LEVELS = {"info": 0, "high": 1, "critical": 2}
_q: "queue.Queue" = queue.Queue(maxsize=1000)
_started = False


def send(level: str, text: str, tenant_chat: str | None, tenant_id: int, push_tokens=None, data=None):
    cfg = settings.get().notifications
    if LEVELS[level] < LEVELS[cfg.min_level]:
        return
    if not (cfg.telegram.enabled and tenant_chat) and not cfg.webhook.enabled and not (cfg.push.enabled and push_tokens):
        return
    _ensure()
    try:
        _q.put_nowait((level, text, tenant_chat, tenant_id, push_tokens or [], data or {}))
    except queue.Full:
        log.warning("notification queue full, dropping")


def _ensure():
    global _started
    if not _started:
        _started = True
        threading.Thread(target=_worker, daemon=True, name="notify").start()


def _worker():
    while True:
        level, text, chat, tenant_id, tokens, data = _q.get()
        cfg = settings.get().notifications
        try:
            if cfg.telegram.enabled and chat:
                httpx.post(f"https://api.telegram.org/bot{cfg.telegram.bot_token}/sendMessage",
                           json={"chat_id": chat, "text": f"[{level.upper()}] {text}"}, timeout=cfg.timeout_seconds)
            if cfg.push.enabled and tokens:
                send_push(tokens, "Solavis", text, data, critical=level == "critical")
            if cfg.webhook.enabled:
                body = json.dumps({"tenant_id": tenant_id, "level": level, "text": text})
                sig = hmac.new(cfg.webhook.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
                httpx.post(cfg.webhook.url, content=body, headers={"Content-Type": "application/json", "X-Solavis-Signature": sig},
                           timeout=cfg.timeout_seconds)
        except Exception as e:
            log.warning("notification failed: %s", e)


def send_push(tokens, title, body, data, critical=False):
    """Expo Push service: one request for up to 100 devices. Works for iOS and Android apps built with Expo or React Native."""
    cfg = settings.get().notifications
    headers = {"Content-Type": "application/json"}
    if cfg.push.expo_access_token:
        headers["Authorization"] = "Bearer " + cfg.push.expo_access_token
    for i in range(0, len(tokens), 100):
        msgs = [{"to": t, "title": title, "body": body, "data": data, "sound": "default", "priority": "high" if critical else "default",
                 "channelId": "alerts", "interruptionLevel": "time-sensitive" if critical else "active"} for t in tokens[i:i + 100]]
        httpx.post("https://exp.host/--/api/v2/push/send", json=msgs, headers=headers, timeout=cfg.timeout_seconds)
