"""The permission catalog. Every permission here guards at least one real endpoint.
Departments choose a ceiling (the most their people can ever hold); heads then hand out rights inside that ceiling."""
CATALOG = {
    "accounts.read":   ("Customers",  "View customers, contacts, notes and the business dashboard"),
    "accounts.write":  ("Customers",  "Create and edit customers; change stage and plan; reset customer sign-ins"),
    "billing.read":    ("Billing",    "View invoices and payments"),
    "billing.write":   ("Billing",    "Create invoices, record payments, void invoices"),
    "plans.write":     ("Billing",    "Edit plans and prices"),
    "support.read":    ("Support",    "View tickets"),
    "support.write":   ("Support",    "Reply to, assign and close tickets"),
    "inventory.read":  ("Inventory",  "View device stock and assignments"),
    "inventory.write": ("Inventory",  "Add units and assign them to customers"),
    "devices.revoke":  ("Inventory",  "Mark a unit returned or lost (disables the camera key)"),
    "tasks":           ("Work",       "Create and complete tasks"),
    "audit.read":      ("Compliance", "Read the audit log"),
    "security.read":   ("Compliance", "Read the security log (sign-ins, face checks) and verify its integrity"),
    "system.read":     ("System",     "See system health and configuration"),
    "staff.read":      ("People",     "View the organisation, roles and access reviews"),
}
MODULES = list(dict.fromkeys(v[0] for v in CATALOG.values()))


def valid(perms):
    return [p for p in perms if p in CATALOG]


def unknown(perms):
    return [p for p in perms if p not in CATALOG]
