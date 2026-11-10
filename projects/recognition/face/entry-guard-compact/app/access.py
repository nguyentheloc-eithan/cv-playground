"""Who may enter right now? The rules that turn "we recognised this person" into granted or denied.

    evaluate(person, cfg)  ->  {"granted": bool, "reason": str, "alert": bool}

Rules, checked in this order (the first one that fails decides):
    1. the person's type cannot enter (blocked / watch list)      -> denied + ALERT
    2. the account is disabled                                    -> denied
    3. "valid from" date has not come yet                         -> denied
    4. "valid until" date has passed                              -> denied
    5. outside the allowed days or hours (person type, else site) -> denied
    otherwise                                                     -> granted
"""
import time
from datetime import datetime

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def person_type(cfg, type_id):
    """The configured type, or a safe fallback for a type that was removed from the config."""
    for t in cfg["person_types"]:
        if t["id"] == type_id:
            return t
    return {"id": type_id, "label": type_id, "can_enter": True}


def _parse_hours(text):
    """'07:00-19:00' -> (420, 1140) minutes since midnight."""
    start, end = text.split("-")
    to_minutes = lambda t: int(t.split(":")[0]) * 60 + int(t.split(":")[1])
    return to_minutes(start), to_minutes(end)


def _fmt_date(ts):
    return datetime.fromtimestamp(ts).strftime("%d %b %Y")


def evaluate(person, cfg, now=None):
    now = time.time() if now is None else now
    kind = person_type(cfg, person.get("person_type", "resident"))

    if not kind.get("can_enter", True):
        return {"granted": False, "reason": kind.get("label", kind["id"]), "alert": True,
                "severity": kind.get("severity", "high")}
    if person.get("status") == "disabled":
        return {"granted": False, "reason": "Account disabled", "alert": False}
    if person.get("valid_from") and now < person["valid_from"]:
        return {"granted": False, "reason": f"Not valid until {_fmt_date(person['valid_from'])}", "alert": False}
    if person.get("valid_until") and now > person["valid_until"]:
        return {"granted": False, "reason": f"Expired on {_fmt_date(person['valid_until'])}", "alert": False}

    days = kind.get("days") or cfg["access"]["days"]
    hours = kind.get("hours") or cfg["access"]["hours"]
    moment = datetime.fromtimestamp(now)
    if DAYS[moment.weekday()] not in days:
        return {"granted": False, "reason": f"Not allowed on {DAYS[moment.weekday()].title()}", "alert": False}
    start, end = _parse_hours(hours)
    minutes = moment.hour * 60 + moment.minute
    if not start <= minutes <= end:
        return {"granted": False, "reason": f"Outside allowed hours ({hours})", "alert": False}

    return {"granted": True, "reason": "", "alert": False}


def status_label(person, cfg, now=None):
    """One word for the People list: active, disabled, blocked, expired or pending (not valid yet)."""
    kind = person_type(cfg, person.get("person_type", "resident"))
    now = time.time() if now is None else now
    if not kind.get("can_enter", True):
        return "blocked"
    if person.get("status") == "disabled":
        return "disabled"
    if person.get("valid_from") and now < person["valid_from"]:
        return "pending"
    if person.get("valid_until") and now > person["valid_until"]:
        return "expired"
    return "active"
