"""Hide sensitive details from people who do not need them (role-based data masking).

A viewer can see WHO was scanned and the access result, but phone numbers and fields marked
`sensitive: true` in the config are shown masked. Admins see everything.
"""


def mask_phone(phone):
    """+84 912 345 678 -> ••••••• 678 (only the last 3 digits stay visible)."""
    digits = [c for c in (phone or "") if c.isdigit()]
    return "" if not digits else "•••••• " + "".join(digits[-3:])


def _sensitive_keys(cfg):
    return {f["key"] for f in cfg["person_fields"] if f.get("sensitive")}


def mask_fields(fields, cfg):
    hidden = _sensitive_keys(cfg)
    return {k: ("••••" if k in hidden and v else v) for k, v in (fields or {}).items()}


def visible(person, cfg, role):
    """A copy of the person (or event) dict that is safe to send to this role."""
    if role == "admin" or not cfg["security"]["mask_for_viewers"] or person is None:
        return person
    safe = dict(person)
    if "phone" in safe:
        safe["phone"] = mask_phone(safe["phone"])
    if "fields" in safe:
        safe["fields"] = mask_fields(safe["fields"], cfg)
    if safe.get("watch"):
        safe["watch"] = {**safe["watch"], "source": "••••", "reference": "••••" if safe["watch"].get("reference") else ""}
    return safe
