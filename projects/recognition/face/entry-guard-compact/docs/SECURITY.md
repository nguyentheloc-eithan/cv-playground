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

## Signing in with the face
There is **one** switch, **Settings > Face authentication**. When it is on, the same enrolled face is used to **sign in**
(login screen: type the user name, press **Sign in with face**, look straight, then turn your head slightly) and to
**confirm risky actions**. The server checks the face against the one that user enrolled (a 1-to-1 check, never a search
over everyone).

- Face sign-in has its **own lockout** (5 failures, 10 minutes, per user and per address), separate from the password's, so
  failed face attempts can never lock someone out of the password login (and cannot be used to attack it).
  A lockout can be cleared from the computer itself: `python main.py unlock USERNAME`.
- Every refused attempt is in the audit log with the reason (`face_authentication_not_switched_on`, `face_not_matching`,
  `account_disabled`, `no_such_user`) and the match scores; the person at the login screen only sees a generic message.
- The password always still works. Disabling a user or changing their password signs them out everywhere.
- Switch face sign-in off for the whole installation with `security.face_login.enabled: false`.

**Be aware (how this differs from a banking app):** banks check the face **on the phone**, with depth/infrared hardware, and the
server only receives a cryptographic signature, never a face. Here a normal webcam picture is compared on the server, so a good
video replay or a 3D mask could pass the head-turn check. For administrators with access to the watch list, prefer the password,
or use passkeys (WebAuthn: Touch ID / Windows Hello) in a later step. The live-feedback endpoint used at sign-in is public (it
must work before login), so it is rate limited and only describes the picture, never an account.

## Confirming risky actions (like a banking app)
Being signed in is not enough for a dangerous action. These need a **fresh confirmation**, every time:
delete a person, **replace, add or remove a person's photos**, add or change a watch-list entry (including switching one off),
create or change a user, delete a camera, export the scan log. (The list is `security.step_up.actions` in the config; remove a line to relax it, or set
`security.step_up.enabled: false`.)

Each user chooses how to confirm in **Settings** with two switches:
- **Face authentication:** look at the camera, then **turn your head slightly** to one side (a progress meter shows how far). A photo or a screen picture cannot do
  that, and the face must also match the face you enrolled (`face_threshold`, stricter than normal recognition).
- **PIN:** a 6-digit PIN (no repeats or simple sequences), entered on a keypad.
- **Password:** always available as the fallback; it is also what turns a method on or off.
When both are on you choose at confirmation time and the one you used last is offered first. Turning a method off,
changing a PIN or enrolling a face needs your password.

How it works: a successful check returns a **one-time token** that is valid for two minutes, only for that user and only
for that action. The page repeats the request with it; the server accepts it once. Wrong attempts count towards the same
lockout as logins (5 failures, 10 minutes). Every confirmation, failure and setting change is in the audit log. A PIN is
stored hashed (scrypt) and a face as numbers, never as a photo.

**Limits:** the head-turn check stops printed photos and screens showing one still picture; a video replay or a 3D mask
could still fool it, so treat it as a convenience layer, not as proof of presence. A confirmation never grants a role:
only admins can perform these actions in the first place.

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

## Fixing a wrong photo
**People > open the person > Update photos** replaces all photos (or adds more) from the camera or from files, and single
photos can be removed (the last one cannot). The new photos get the same checks as at registration, and a face that already
belongs to **someone else** is refused. Changing the face that opens the door is an identity change, so it needs a
confirmation and is audited (`person_photos_changed`). The old face stops being recognised straight away.

The head turn is deliberately small (`security.step_up.head_turn_min_yaw: 0.20`). A larger value is stricter against held-up
photos; `require_head_turn: false` removes the turn entirely (weaker).

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
- No two-factor login (TOTP / passkeys) at sign-in yet; step-up confirmation protects risky actions after sign-in.
- The audit chain detects edits and deletions in the middle; removing only the newest lines is not detected.
  Keep an off-site copy of the exported log for stronger guarantees.
- HTTPS is not terminated by the app. Put Caddy in front (see the setup guide in the specification), then set
  `auth.secure_cookie: true`.
- Access decisions are shown and logged; the app does not open a door yet (no relay / actuator).
