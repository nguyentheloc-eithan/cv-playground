# AI and computer vision

## Pipeline (edge detect, cloud recognise)
```
Camera (PIR wake) -> capture frame -> [face crop] --HTTPS--> Device API
Cloud: decode -> YuNet detect -> pick largest face >= min_face_px -> SFace embed (128-d)
     -> compare against that tenant's vectors (cosine = dot of L2-normalised vectors)
     -> verdict: known | uncertain | unknown   (+ watch-list branch)
     -> store crop (not the full frame) -> alert rules -> owner reviews
```
Models (OpenCV ONNX, CPU only): **YuNet** face detector, **SFace** recogniser producing 128-number vectors. Both run through OpenCV's DNN module; no GPU, no heavy framework.

## Decision logic
| Score (cosine) | Verdict | Action |
|---|---|---|
| >= 0.363 (accept) | known | log event, name shown |
| 0.30 to 0.363 | uncertain | treated as not identified, flagged for review |
| < 0.30 (reject) | unknown | "Unknown person" alert (info) |
| watch-list person >= 0.45 | "Likely" match | high alert, **human must verify** |
| watch-list person < 0.45 | "Possible" match | high alert, human must verify |

Thresholds 0.363 / 0.30 are the published SFace operating point and are **not tuned on my own data**. All values live in `recognition.yaml`; no code change to tune. Honest status: accuracy is **not measured**; a labelled evaluation set is a next step (see prompt-task, Task 5).

## Design choices worth showing
- **One model for two jobs.** The same face engine serves visitor recognition and the President's face login, with different thresholds (0.363 for visitors, 0.50 for admin login).
- **Thread-safe inference.** OpenCV models are not thread-safe; a lock serialises inference while the web layer stays async.
- **Per-tenant matching.** Vectors are queried by `tenant_id`; a customer can never match another customer's people. Tests try to cross the boundary.
- **Plan-gated features.** Watch-list only runs if the plan includes it.
- **Idempotent events.** Each upload carries an idempotency key so a retry over a bad 4G link never double-counts or double-alerts.
- **Privacy by design.** Store the face crop, not the frame; consent note required to register a person; delete a person erases photos and vectors; retention per event class (unknown 30 d, known 90 d, alerts 180 d); the camera holds no faces and no storage keys.
- **Wording discipline for sensitive AI.** Watch-list results are never called "identified". The UI says "possible match" and requires human review before any action.

## Face login with liveness (President)
- Enrolment from a one-time code (hashed, 24 h): two webcam frames, straight then head turn.
- Verification: SFace match >= 0.50 **and** head-turn yaw >= 0.20 from landmark geometry (pose estimate from the 5 detector landmarks).
- Lockout after 3 failures in 15 min; every attempt stores the captured frame in the tamper-evident log.
- Fresh re-verification (10 min) required for sensitive actions; server answers HTTP 428 and the browser pops the camera dialog, then retries.
- Known gap (state it): head-turn is a basic liveness cue; a determined printed-photo or replay attack is only partly covered.

## Image-based tamper check (classic CV, no ML)
The camera sends a small grayscale frame at check-in. The server builds a 32-bin histogram (64×48 downscale) and compares it with the frame stored at arming using histogram correlation. Below 0.55 means the view changed or the lens is covered, so the camera locks. Cheap, needs no extra part, runs server-side.

## What to say in an interview
- Why cloud recognition: ESP32-class chip cannot run the full model, and a stolen camera then exposes nothing.
- Why thresholds are config: tuning per site (lighting, lens) without a firmware update.
- What I would do next: build an evaluation set (genuine/impostor pairs), plot ROC/DET, pick thresholds per lens and lighting, add a stronger liveness model, consider on-device detection quantised for ESP32-S3.
