# Security model

What the app does to protect an entrance, and what it does not (yet).

## Access decisions
Recognising a face is not the same as allowing entry. After a match the system applies **access rules**
(`app/access.py`, configured in `config/default.yaml`) and records both results on every scan:

| Order | Rule | Result |
|---|---|---|
| 1 | Person type cannot enter (`can_enter: false`, e.g. Blocked / watch list) | Denied, **alert** |
| 2 | Account disabled | Denied |
| 3 | "Valid from" date not reached | Denied |
| 4 | "Valid until" date passed | Denied |
| 5 | Outside the allowed days / hours (per person type, else site-wide) | Denied |
| - | None of the above | Granted |

Disabled, expired and blocked people are still **recognised**, so the console can say "Access denied: Expired
on 05 Nov" instead of showing a stranger. Denied scans keep a snapshot and are queued for review.

## Watch list: criminals and banned people
Staff can add people to a **watch list** (person types `criminal` and `blocked`, configurable) by typing the details and
**uploading photo files** (or capturing them). Every entry needs a **reason** and a **source**, may carry a case number,
instructions for staff and a "review by" date (overdue reviews are flagged), and records who added it and when.
Instead of the person's consent, the operator ticks a **legal-basis confirmation**.

A detection of a watch-list person:
- always **denies access**, keeps a snapshot and opens an **alert** that stays open until someone acknowledges it
  (the acknowledgement records who and what was done);
- **critical** (type `criminal`, confirmed match): full-screen red overlay with a repeating siren on every staff screen,
  Esc cannot dismiss it; **high** (type `blocked`, or a criminal only *possibly* matched): flashing banner;
- is announced to **residents** (a user with the `resident` role, and any configured Telegram / webhook channel):
  a short warning with the photo, **no name, no offence, no ID**, and an instruction not to open doors or approach;
- is sent to **security** channels with the full details, the instructions and "verify identity before acting".

**False matches:** face recognition can be wrong, and a false accusation does real harm. A criminal match is only
critical when the score reaches `alerts.watchlist_confirm_score` (default 0.45, above the normal accept threshold);
a weaker match is raised as a **possible match** (high) with a verify-first warning. Tune this with your own footage.

**Legal:** records about criminal behaviour are highly sensitive personal data in most countries and their use is often
restricted. Only enter information you are legally authorised to hold and share, from a reliable source, review it
regularly and delete it when it is no longer needed. Check local law before notifying residents.

Notifications are off by default. Add channels in your customer file (secrets come from environment variables):
```yaml
alerts:
  channels:
    - { type: telegram, audience: security,  token: "${TELEGRAM_BOT_TOKEN}", chat_id: "${TELEGRAM_SECURITY_CHAT}" }
    - { type: telegram, audience: residents, token: "${TELEGRAM_BOT_TOKEN}", chat_id: "${TELEGRAM_RESIDENTS_CHAT}" }
    - { type: webhook,  audience: residents, url: "${RESIDENT_ALERT_WEBHOOK}", photo: false }   # SMS gateway, Home Assistant...
```

## Registration safeguards
- Phone, unit and person type are validated; a phone number cannot be registered twice.
- **A face that already belongs to someone is refused** (`block_duplicate_faces`), which stops double identities.
- Photos must be sharp, front-facing, one face, big enough; consent is required and its time and text version are stored.
- Every person gets an automatic ID (`APT-00042`, prefix per customer).

## Accounts and sessions
- Passwords: scrypt hash, minimum length (default 12), no repeated characters, must not contain the user name.
- **Lockout:** 5 wrong passwords lock the account for 10 minutes (also limited per address).
- Sessions are signed HttpOnly, SameSite=Strict cookies. Changing a password, role or active flag **signs the user out everywhere**.
- Roles: `admin` (manage everything), `viewer` (watch, review) and `resident` (sees safety alerts only: no names,
  no personal data, no other page or API). Viewers see phone numbers and fields marked `sensitive: true` **masked**,
  and the watch-list source and case number masked (the reason and instructions stay visible, staff need them to act).
- The last active admin cannot be disabled or demoted; nobody can lock themselves out.

## Web protection
- CSRF: every change request must carry `X-Requested-With: entryguard` and a matching `Origin`.
- Headers on every response: Content-Security-Policy (scripts only from this app), `X-Frame-Options: DENY`,
  `nosniff`, `Referrer-Policy: no-referrer`, camera allowed for this site only; API answers are `no-store`.
- Camera passwords are never returned by the API and never written to the audit log.

## Audit
Every login, failed login, lockout, person change, access to exports and camera change is logged with who and when.
Each audit line is **hash-chained** to the previous one; **Audit log > Verify integrity** detects edited or removed lines.

## Known limits (next steps)
- Photos, face vectors and camera passwords are stored **unencrypted** in `data/`. Turn on FileVault (Mac) or BitLocker
  (Windows), and restrict who can read the folder. Application-level encryption at rest is a later step.
- No anti-spoofing yet: a printed photo or a phone screen can be accepted as a real face. Add a liveness check
  before relying on this for access to a door.
- No two-factor login (TOTP / passkeys) yet.
- The audit chain detects edits and deletions in the middle; removing only the newest lines is not detected.
  Keep an off-site copy of the exported log for stronger guarantees.
- HTTPS is not terminated by the app. Put Caddy in front (see the setup guide in the specification), then set
  `auth.secure_cookie: true`.
- Access decisions are shown and logged; the app does not open a door yet (no relay / actuator).
