# C-UAS Vision Platform

Counter-UAS · Video analytics · Architecture plan

Video analytics that finds and tracks small drones. Video or frames go in, drone detections and tracks come out. Built like a car: a fixed chassis with standard sockets, so a broken part is replaced by a temporary one and repaired or upgraded alone.

**Python first for the baseline, C++ only where a benchmark says it is needed.**

---

## 01 · Scope

**Frames in, drones out.** The system receives video or frames, detects drones, tracks them over time, separates them from birds and clutter, and reports the result with evidence. It does not control sensors, weapons or other systems.

**Input**
- Video file, RTSP stream or camera (visible or thermal)
- Each frame carries a capture timestamp and a camera id

**Output**
- Per frame: boxes, class (drone or not), confidence, track id
- A degraded flag when a fallback part is running
- On a confirmed track: an event with a short evidence clip

**Out of scope**
- Radar and RF sensors, sensor fusion
- PTZ control, threat policy, C2 integration
- Any effector or response

Future extension: a radar or RF feed would be one more input adapter behind the same tracker interface. No detector change is needed, so none of that is designed now.

---

## 02 · C++ or Python?

**Hybrid target, Python first.** Build the baseline in Python, measure latency and throughput on the real hardware, and port only the modules that miss the requirement to C++ behind the same interfaces. Training, evaluation and tooling stay in Python. The two sides meet at a TensorRT/ONNX model file, a protobuf schema and a YAML config.

Python already runs TensorRT, OpenCV and other native libraries, and most inference time runs outside the interpreter, so the GIL is not automatically the bottleneck. C++ adds cost in memory ownership, concurrency, build and debugging.

| Concern | C++20 | Python 3.11 |
|---|---|---|
| Frame-loop latency and jitter | Tighter control of memory and concurrency; meets strict latency if designed and tuned well | Meets many inference workloads through native libraries; jitter and throughput limits must be measured |
| GPU path (NVDEC, CUDA, TensorRT) | Device memory stays on the GPU from decode to inference | Bindings exist; extra copies are easy to introduce |
| 24/7 edge uptime, memory control | Deterministic ownership (RAII), small footprint on Jetson | Leaks and fragmentation need soak testing |
| Model iteration speed | Slow. Long builds, heavy tooling | Fast. PyTorch, Ultralytics, notebooks |
| Data, labeling, evaluation | Poor | Richest ecosystem |
| Hiring and team cost | Narrower pool | Wide pool |

Rule: no module moves to C++ until a benchmark on target hardware shows Python misses the p95/p99 latency or throughput requirement for that module.

---

## 03 · Pipeline architecture

Ports and adapters. The video source, detector, tracker and output each sit behind an interface, so the same pipeline runs on a live camera, a recorded file or a test fixture.

```
FRAME PATH · pooled GPU buffers, handles only

VideoSource → Decode → Preprocess → Detector → Tracker → Classifier → ResultSink
RTSP · file   NVDEC    tile+resize  TensorRT   Kalman    bird vs      boxes · clips
                                    · GPU      + match   drone            │
                                                                           ▼
                                                                       Recorder
                                                                   clip + track log
═══ In-process event bus (metadata) · Health & metrics · Config · Audit log ═══
```

Frames move stage to stage through bounded queues. Only metadata (detections, tracks, alerts, health) goes on the event bus. The classifier scores each track over several frames, so a bird that looks like a drone in one frame is rejected by its flight pattern.

### Three kinds of data movement

| Layer | Carries | Mechanism | When it exists |
|---|---|---|---|
| Pipeline | Video frames between stages, with backpressure | Bounded queues (drop-oldest) holding handles to pooled buffers, inside one process | From the MVP |
| Event bus | Metadata: detections, tracks, alerts, health | In-process pub/sub first; same interface later backed by ZeroMQ | In-process from the MVP |
| IPC | The same events between processes | ZeroMQ or similar, protobuf | Only when a module needs its own process |

Protobuf defines message structure; it does not provide zero-copy. Frames never travel through the serialized bus.

### Process and thread model (MVP default)

**One Python process** that calls native libraries (NVDEC/GStreamer, OpenCV, TensorRT). Hot-path modules ported to C++ later load **in the same process as Python extensions** (pybind11 or similar), so frames stay in GPU memory. A separate process is used only where isolation is worth the cost, such as a vendor camera SDK that can crash.

```
Process "edge_node"
 ├─ thread: capture/decode per camera ─► [frame pool] ─► queue (drop-oldest)
 ├─ thread: preprocess/tile + detect  ─► Detections (metadata)
 ├─ thread: tracker + classifier      ─► Tracks
 ├─ thread: result/evidence writer    ─► sink, recorder (async, retried)
 └─ in-process event bus: metadata, health, alerts
Separate processes, only when needed: vendor SDK wrapper, ops API, training tools
```

**Frame ownership.** A frame lives in a fixed pool of buffers. The source takes a buffer, fills it and hands a handle downstream. Each stage holds a reference only while it uses the buffer and releases it when done. A frame dropped from a full queue releases its buffer at once. Metadata copies what it needs (timestamps, boxes) and never keeps a buffer alive. Evidence crops are copied out explicitly.

### Deployment

- **Edge node:** Jetson Orin or x86 + RTX. Runs the whole pipeline next to the camera. Docker, read-only root, signed images.
- **Training environment:** Separate GPU machine, Python. Produces versioned model files that the edge node loads after checking their signature.

---

## 04 · Swappable modules

The system is a chassis with sockets, like a car. When a part breaks, a temporary part is fitted so the vehicle keeps running, and the broken one is repaired on the bench. A part can also be upgraded alone. No other part is touched, because parts only meet at the socket.

**Verdict: good, with conditions.** Four sockets are enough for this scope. It only works if the socket contracts stay small and stable, and every limp-home part is tested as seriously as the main one.

```
CHASSIS (fixed, rarely changes)
Supervisor · Component registry · Health monitor · Event bus · Config

SOCKETS (versioned interfaces)
IVideoSource       IDetector            ITracker             IResultSink
     │                  │                    │                    │
PRIMARY PART
RtspSource         TrtDetector          ByteTrackTracker     StreamSink
[active]           [GPU FAULT]          [active]             [active]
                        │ failover
LIMP-HOME PART (standby)
BackupRtsp         MotionDetector       KalmanIouTracker     LocalFileSink
second stream      CPU · ACTIVE now     simple, no re-ID     buffer and retry
                   unclassified
```

The detector socket shows a live swap: the GPU detector is out for repair and a CPU motion detector keeps the site alarming at lower accuracy. The tracker and sink never notice.

**A limp-home part is not an equal replacement.** `MotionDetector` finds movement but cannot classify objects, so a motion-only site cannot tell a drone from a bird. Output from a degraded detector carries the degraded flag and the class "unclassified", and is never reported as a confirmed drone.

### Patterns used

| Pattern | Where | What it buys |
|---|---|---|
| Strategy | `IDetector`, `ITracker` | Swap algorithms or A/B test models with a config change |
| Adapter | Video sources | Camera and protocol details stay out of the core; one fake source for tests |
| Decorator | `TiledDetector`, `ClassifiedDetector` | Tiling and bird rejection added without touching model code |
| State | `Track` lifecycle: Tentative → Confirmed → Coasting → Lost | Confirmation and loss rules in one tested place |
| Supervisor + limp-home | Each socket has a primary and a fallback | Temporary replacement on fault; shadow run before switching back or promoting an upgrade |

```python
# core/interfaces.py  (a C++ mirror is written only when a module is ported)
@dataclass
class Detection:
    box: BBox            # pixels, sensor frame
    score: float         # detector score, not a probability
    cls: ClassId
    frame_ts: float      # capture time
    camera_id: str

class IDetector(Protocol):
    def warmup(self) -> None: ...
    def detect(self, frame: FrameHandle) -> list[Detection]: ...
    def health(self) -> Health: ...        # mode, last error, heartbeat age
    def info(self) -> ModelInfo: ...

# config: detector: { primary: trt_yolo, fallback: motion_cpu, shadow: trt_rtdetr }
```

### The three garage operations

| Operation | What happens | What stays untouched |
|---|---|---|
| Temporary replacement | Health monitor sees missed heartbeats or errors, the Supervisor rebinds the socket to the limp-home part at the next frame, and sets the degraded flag | Every other module |
| Repair the official part | Fix runs on the bench against the replay set and contract tests, then the Supervisor switches back after a warm-up and a clean shadow run | The limp-home part keeps serving until the switch |
| Upgrade a part | New model registers under a new version, runs in shadow beside the old one, then is promoted by config. Rollback is one config line | All other parts and the socket contract |

### Failure and recovery rules

`health()` only reports. The Supervisor acts on it with explicit rules. Values are starting points, to be tuned in phase 4.

| Failure | Detected by | Action |
|---|---|---|
| Camera disconnect | No frame for 2 s | Mark source down, reconnect with exponential backoff (1 s up to 30 s), report it, keep other cameras running |
| GPU reset or CUDA error | Inference call error, driver log | Rebuild the inference context, warm up, resume; if it fails 3 times in 10 min, go to degraded mode |
| Stage hung | No heartbeat for 5 s | Restart the stage; if a thread cannot be stopped, restart the process |
| Queue full for a long time | Drop rate above threshold for 30 s | Warn, then shed load (lower rate or fewer tiles) and set the degraded flag |
| Process crash | Service manager | Restart, reload config and model, rebuild tracks from scratch and mark them "re-acquired" |
| Result sink unreachable | Send error or timeout | Buffer results on local disk, retry with backoff; never block the frame loop |

**No flapping.** A part that fails is failed over once. Failback needs a minimum dwell time in degraded mode and a clean shadow run (for example 60 s with no errors), and is allowed at most a fixed number of times per hour. After that the part is latched out until an operator or an automated repair step clears it. Every transition is written to the audit log.

### MVP scope

| Build now | Defer until operations show the need |
|---|---|
| Four interfaces: `IVideoSource`, `IDetector`, `ITracker`, `IResultSink` | Plugin registry, abstract factories |
| Video file adapter, then RTSP and live camera | Hot-swap of every module |
| Replay regression, structured logging, metrics | General shadow deployment |
| Versioned protobuf schemas | Several implementations per interface |
| Health monitoring and visible degraded flag | Distributed messaging |

Slice: video file → detector → tracker → result and evidence. Only modules that truly need runtime failover get a limp-home part; the rest change through deployment or config.

### Pros and cons

**Pros**
- A fault stays in one part, and a stand-in keeps detection running during the fix
- Upgrade the detector or tracker without regression risk to the rest
- Shadow mode gives A/B model tests on live video
- Parts test alone with fakes and recorded video
- Camera SDK lock-in stays inside one adapter

**Cons**
- A wrong socket contract is costly because every part depends on it
- Frames crossing a boundary can add copies, so they stay in pooled GPU buffers
- A generic socket can hide a part's special features (GPU batching)
- Limp-home parts get neglected, and results change silently on failover
- More to operate: versions, health rules, compatibility

---

## 05 · Latency budget

Working allocation for one stream at 1080p with tiling. It is a placeholder to design against, not an acceptance criterion. Stages run in parallel, so the total does not translate to a final frame rate.

| Stage | Budget |
|---|---|
| Capture + NVDEC decode | 12 ms |
| Preprocess + tile | 6 ms |
| **Inference** | **25 ms** |
| Track | 4 ms |
| Classify | 4 ms |
| Publish | 3 ms |
| **Total** | **54 ms** |

It becomes an acceptance criterion only when these are fixed and measured on the real device:

- GPU model and power mode, camera count, resolution and frame rate
- Tiles per frame and batch size
- Average, p95 and p99 latency, not just the mean
- Throughput with all cameras running at once
- End-to-end latency from camera exposure to the result being published

Also: bounded queues with drop-oldest, so a slow stage drops stale frames and never builds a backlog; and every frame is timestamped at capture and carried through to the result, so latency is measured, not guessed.

---

## 06 · What makes drone detection hard

- **Tiny targets.** A small quadcopter at range is a few to a few dozen pixels. Use tiled inference over full-resolution frames, a stride-4 detection head, long focal length, and train on crops that match the real pixel sizes.
- **Birds and clutter.** Birds, insects, kites and aircraft cause false alarms. Add a second-stage classifier on the track crop, and score motion over time (wingbeat, flight path), not single frames.
- **Day, night, weather.** Support visible and thermal video. Keep one model per modality or a fused-input model, and gate each by image quality metrics.
- **Moving camera.** PTZ and vehicle-mounted cameras move. Estimate ego-motion so the tracker works on stabilized coordinates, and the motion detector subtracts camera movement.
- **Metrics that matter.** Probability of detection by range band; false alarms per camera-hour; time from first visible to confirmed track; track continuity (ID switches).

### Output schemas

| Schema | Holds |
|---|---|
| `Detection` | capture timestamp, frame id, camera id, box in pixels, detector score, class scores |
| `Track` | track id, camera id, state (tentative, confirmed, coasting, lost), box history, velocity in pixels, class probabilities, first-seen and last-seen time, degraded flag |
| `DroneEvent` | track id, confirmation time, class probabilities, evidence clip path, model and config versions |

Detector score is not the probability that the object is a drone. Class probabilities are kept as their own field and are calibrated on the test set.

### Evaluation protocol

Detection numbers only mean something if the test data is independent of the training data.

- Split by recording session, and where possible by site, date or condition, never by frame. Neighboring frames of one video must not appear on both sides.
- Keep a held-out set of scenarios that never appear in training: new site, new drone model, night, bad weather.
- Version the labeling guide, the labels, the split and the metric definitions together with the frozen test set.
- Report sample counts and uncertainty with every metric, for example a confidence interval on Pd per range band.
- Measure false alarms per camera-hour on long background-only recordings, separate from the Pd test set.

---

## 07 · Repository and stack

```
cuas/
├── core/        interfaces, Detection, Track, pipeline, supervisor
├── sources/     VideoSource adapters (file, RTSP, GigE)
├── detect/      detectors, tiling, track classifier
├── track/       Kalman, ByteTrack
├── sinks/       JSON, stream, evidence recorder
├── apps/        edge_node (composition root)
├── proto/       protobuf schemas = the public contract
├── ml/          training, export (ONNX → TensorRT), evaluation
├── tools/       replay, dataset tools, ops API
├── deploy/      Dockerfiles, compose, signing
└── tests/       unit (fake sources), replay regression, hardware-in-the-loop
```

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.11 first; C++20 for measured hot paths | Fast iteration, port only what the benchmark requires |
| Video and GPU | GStreamer or DeepStream, NVDEC, CUDA, TensorRT | Hardware decode and GPU-resident frames |
| Models | YOLO-family or RT-DETR, trained in PyTorch | Mature export to TensorRT; compare on your own data |
| Messaging | In-process first, protobuf schemas, ZeroMQ if processes split | No distributed layer until needed |
| Observability | Prometheus, Grafana, structured logs | Per-stage latency and detection quality on one screen |
| Integrity | Signed images and models, versioned config, audit log of swaps | Know exactly which model produced a result |
| CI/CD | Replay regression on a fixed video set gates every merge | A change cannot silently lower Pd or raise false alarms |

---

## 08 · Roadmap

Durations are indicative for a team of 3–5. They are an estimate, not a commitment, until the open questions at the end are answered.

**Phase 0 · 2–3 weeks — Requirements and data.** Fix the target hardware, cameras and input types. Define test conditions (range bands, day and night, weather), the independent evaluation data, the labeling method, and numeric thresholds for Pd, false alarms per camera-hour and latency. Collect drone, bird and background footage from the real cameras.
*Exit: signed requirements with numeric thresholds, and a labeled seed dataset.*
*Gate 1: do not move on without target hardware, usable test data with ground truth, the evaluation protocol and agreed acceptance criteria.*

**Phase 1 · ~6 weeks — Python vertical slice.** Video file → detector → tracker → result and evidence clip, in Python, with replay and evaluation harness, metrics, logging and versioned schemas. Benchmark on the target hardware.
*Exit: Pd and false-alarm numbers per range band on a frozen test set, plus measured p95/p99 latency and throughput on real hardware.*
*Gate 2: end-to-end run on target hardware with detection, false-alarm, latency, throughput and replay-regression results. The process model, frame ownership and recovery rules are decided here from the measurements.*

**Phase 2 · set by phase 1 — Port the hot path.** Move only the modules that missed the requirement to C++ (likely decode, preprocess, inference), behind the same interfaces. Add the frame buffer pool and bounded queues. Add live RTSP input.
*Exit: live stream under the measured requirement, replay regression green.*
*Gate 3: the same workload run before and after each port, comparing accuracy, latency, throughput and resource use. A port that does not improve a missed requirement is reverted.*

**Phase 3 · 6–8 weeks — Detection robustness.** Work condition by condition: tiny and distant targets, birds and clutter, night and thermal, moving camera. Mine hard cases, retrain, and add the track classifier and ego-motion where the evaluation shows they are needed.
*Exit: each condition meets its threshold on the held-out set.*
*Gate 4: no condition is declared done on training or seen-site data.*

**Phase 4 · ~4–6 weeks — Hardening.** Soak tests of 7 days or more on edge hardware, and failure injection: camera loss, GPU reset, process crash, sink unreachable, degraded mode and recovery. Add model and config versioning with rollback.
*Gate 5: all injected failures recover within the rules above, and no failure flaps between primary and fallback.*

**Phase 5 · ongoing — Operate and improve.** Collect hard cases, retrain, ship signed models with versioning and rollback, and track model drift and the false-alarm rate.

---

## 09 · Main risks

| Risk | Impact | Mitigation |
|---|---|---|
| Too little real drone footage at long range | High | Early field collection, synthetic data for augmentation only, test set always from real cameras |
| False alarms from birds | High | Second-stage classifier, temporal scoring, per-site threshold tuning, report false alarms per hour from day one |
| Train and test data leak into each other | High | Split by session and site, held-out scenarios, versioned split, uncertainty with every metric |
| Latency target never validated on real hardware | High | Fix hardware and workload in phase 0, report p95/p99 from the phase 1 benchmark |
| Limp-home part drifts or is never tested | High | Same contract tests and replay set as primaries, degraded flag on every output, scheduled failover drills |
| Framework built before the model and data are proven | High | Vertical slice first; registry, hot-swap and shadow deployment only on demonstrated need |
| Model accuracy drops after a change | Medium | Frozen replay set gating CI, model registry with rollback |
| Socket contract set wrong early | Medium | Four coarse sockets, versioned messages, freeze the contract after the phase 1 baseline |
| Vendor lock-in on GPU or camera SDK | Medium | Vendor code behind adapters; ONNX kept as the portable model format |
| C++ team ramp-up | Medium | Keep the C++ surface small and benchmark-driven; sanitizers and clang-tidy in CI |

---

## 10 · Open questions before approving the full build

1. Is the target hardware Jetson Orin or x86 with an NVIDIA RTX GPU? How many cameras, at what resolution and frame rate?
2. What inputs are needed: recorded files only at first, or live RTSP and thermal cameras too?
3. Is there real footage with ground truth, especially at long range and at night?
4. What are the acceptance thresholds for latency, false alarms, detection performance and simultaneous cameras? They have no values yet and must be agreed from the use case and camera limits. Until then phase 1 cannot be declared a success and no schedule is committed.
5. Who consumes the output (JSON, a stream, a viewer), and in what format?
6. Which modules need runtime failover, and which only change through deployment or config?
