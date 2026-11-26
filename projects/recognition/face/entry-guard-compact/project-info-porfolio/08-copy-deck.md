# Copy deck (edit freely, keep facts within the truth ledger)

## Title
Solavis: a solar-powered AI gate camera with a cloud that runs the business

## Status badge
Software built and tested · Hardware in design · Pilot planned

## Hero sub-line
Face recognition at the gate, layered tamper protection, and a full company back office. Designed and built end to end by one engineer.

## Card text (project grid, ~30 words)
A gate camera that runs on sunlight, recognises visitors, and locks itself when moved. Python cloud, face AI, ESP32 hardware design, and an enterprise ERP with face-secured admin.

## Three headline stats (only these)
- **157** automated tests passing
- **5** layers of tamper detection
- **~0.5 to 0.8 Wh/day** estimated energy target (not measured)

## Section blurbs
**AI.** Camera detects, cloud recognises: YuNet finds faces, SFace turns them into 128-number vectors, cosine scores decide known, uncertain or unknown. Watch-list matches always need a human.

**Hardware.** ESP32-S3 with LTE, solar charger, 18650 cell, PIR, accelerometer, compass and a reed switch. A 125 × 90 × 79 mm wedge enclosure generated from code.

**Tamper.** Accelerometer, compass, magnet switch, image comparison and missed check-ins. Any one trips a lock; only the owner unlocks.

**Cloud.** Multi-tenant FastAPI backend. Plans and limits are data; a suspended account stops uploading on the next wake-up.

**Security.** President signs in with password and live face. Rights are delegated by department ceilings. Every action lands in a hash-chained log.

## CV paragraph (about 70 words)
Solo designer and engineer of Solavis, a solar-powered AI gate camera and subscription platform. Built the multi-tenant FastAPI cloud, OpenCV face-recognition pipeline (YuNet and SFace), server-side layered tamper detection, a customer app and an enterprise ERP with department-delegated access, face-verified super admin and a tamper-evident audit log (157 tests). Designed the ESP32-S3 low-power hardware, energy budget and a code-generated 3D-printable enclosure. Hardware is in design; pilot planned.

## CV bullets
- Designed layered tamper protection (accelerometer, compass, reed switch, image histogram, missed check-ins) with server-authoritative lock state.
- Implemented face-verified super-admin login with head-turn liveness, re-verification for sensitive actions and a hash-chained security log.
- Built dynamic RBAC: department ceilings, head-managed roles, per-person grants and denials, with tests for privilege escalation.
- Wrote a hardware spec with energy budget, sensor selection rationale and a verification plan; generated the enclosure in Python.

## LinkedIn post (draft)
I have been building Solavis, a solar-powered AI gate camera. The cloud side is working against a simulator: face recognition, a tamper state machine that locks the camera when it is moved or turned, plans and limits per customer, and an ERP where the President signs in with a live face check. The hardware is designed (ESP32-S3, 4G, solar) and the enclosure is generated from code. Next: bench tests and a small pilot. What I learned: a tilt sensor alone cannot see a turn, so tamper detection must be layered.

## Do not write
"Deployed", "customers", "99% accuracy", "military-grade", "IP67", any price.
