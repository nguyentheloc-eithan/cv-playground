# C-UAS Vision Platform

Counter-UAS · Video analytics · Architecture plan

An object-oriented, enterprise architecture for detecting, tracking and classifying small drones from video, fused with radar and RF. Built like a car: a fixed chassis with standard sockets, so a broken part is replaced by a temporary one and repaired or upgraded alone.

**Use both languages: C++ for the real-time runtime, Python for everything that trains, evaluates and operates around it.**

---

## 01 · C++ or Python?

**Hybrid target, Python first.** The target is C++20 for the always-on pipeline (capture, decode, inference, tracking, fusion, alerting) and Python for training, dataset tooling, evaluation, simulation and dashboards. They meet at three artifacts: a TensorRT/ONNX model file, a protobuf schema, and a YAML config.

C++ is not assumed up front. Python can already run TensorRT, OpenCV and other native libraries, and most inference time runs outside the interpreter, so the GIL is not automatically the bottleneck. C++ adds cost in memory ownership, concurrency, build and debugging. The baseline is built in Python, latency and throughput are measured on the real hardware, and only the parts that miss the requirement are ported to C++ behind the same interfaces.

| Concern | C++20 | Python 3.11 |
|---|---|---|
| Frame-loop latency and jitter | Tighter control of memory ownership and concurrency; can meet strict latency if designed and tuned well | Meets many inference workloads through native libraries; overhead, jitter and throughput limits must be benchmarked on the real workload |
| GPU path (NVDEC, CUDA, TensorRT) | Fits. Zero-copy device memory from decode to inference | Possible. Bindings exist, extra copies are easy to introduce |
| 24/7 edge uptime, memory control | Fits. Deterministic ownership (RAII), small footprint on Jetson | Risky. Leaks and fragmentation are harder to bound |
| Camera, radar and DDS SDKs | Fits. Vendor SDKs ship C/C++ first | Wrappers. Often thin or missing |
| Model iteration speed | Slow. Long builds, heavy tooling | Fits. PyTorch, Ultralytics, notebooks, fast experiments |
| Data, labeling, evaluation, MLOps | Poor | Fits. Richest ecosystem |
| Operator tools, APIs, dashboards | Possible | Fits. FastAPI, plotting, quick UIs |
| Hiring and team cost | Narrower pool | Wide pool |

### What lives where

**C++ — runtime**
- Sensor adapters and ingest
- Decode, preprocess, tiling
- Detector inference (TensorRT)
- Tracker, fusion, threat scoring
- Alert and C2 gateway, recorder

**Python — lifecycle**
- Dataset curation and labeling
- Training, export to ONNX/TensorRT
- Offline evaluation and replay harness
- Simulation and synthetic data
- Ops dashboard and reporting API

Rule: no module moves to C++ until a benchmark on target hardware shows Python misses the p95/p99 latency or throughput requirement for that module.

---

## 02 · Enterprise architecture

Hexagonal (ports and adapters) core. Every external thing, whether a camera, radar, model runtime or C2 system, sits behind an interface, so the core logic runs identically against live sensors, recorded files or simulators.

```
SENSORS        INGEST          PERCEPTION        TRACK & FUSE       DECIDE & REPORT
EO/IR camera → VideoSource  → Tiler+Detector  → Tracker ─────┐     ThreatAssessor
                                                 (2D tracks)  ▼       ▲   │
Radar        → RadarSource  ──────────────────→ FusionEngine ─────────┘   ▼
RF detector  → RFSource     ──────────────────→ (global picture)       AlertGateway
                                                                          │
                                                                          ▼
                                                                    EvidenceRecorder
═══ Event bus (ZeroMQ / DDS, protobuf) · Config service · Health & metrics (Prometheus) · Audit log ═══
```

Radar and RF join at the fusion engine, not at the detector, so video detection stays a pure image problem. Fusion can also cue a PTZ camera to a radar track (a `Command` sent back through the bus).

### Three kinds of data movement

The diagram's "event bus" is not one thing. Keeping these three apart avoids building overlapping messaging layers.

| Layer | Carries | Mechanism | When it exists |
|---|---|---|---|
| Pipeline | Video frames between stages, with backpressure | Bounded queues (drop-oldest) holding handles to pooled buffers, inside one process | From the MVP |
| Event bus | Metadata only: detections, tracks, alerts, health, commands | In-process pub/sub first; same interface later backed by ZeroMQ/DDS | In-process from the MVP |
| IPC / broker | The same events between processes or nodes | ZeroMQ, DDS or MQTT, protobuf | Only when a module must run in its own process or on another node |

Protobuf defines message structure; it does not provide zero-copy. Frames never travel through the serialized bus.

### Process, thread and language model (MVP default)

Default for the MVP: **one Python process** that calls native libraries (NVDEC/GStreamer, OpenCV, TensorRT). Hot-path modules ported to C++ later are loaded **in the same process as Python extensions** (pybind11 or similar), so frames stay in GPU memory and are not copied or serialized. A separate process with IPC is used only where isolation is worth the cost: a vendor SDK that can crash, a module on another node, or the training/ops tools.

```
Process "edge_node"
 ├─ thread: capture/decode per camera ─► [frame pool] ─► queue(drop-oldest)
 ├─ thread: preprocess/tile + detect  ─► Detections (metadata)
 ├─ thread: tracker                   ─► Tracks
 ├─ thread: fusion (later)            ─► FusedTracks
 ├─ thread: alert/evidence writer     ─► C2, recorder (async, retried)
 └─ in-process event bus: metadata, health, alerts
Separate processes (only when needed): vendor SDK wrapper, ops API, training tools
```

**Frame ownership:** a frame lives in a fixed pool of buffers. The source takes a buffer, fills it and hands a handle downstream. Each stage holds a reference only while it uses the buffer and releases it when done. A frame dropped from a full queue releases its buffer at once. Metadata copies what it needs (timestamps, boxes) and never keeps a buffer alive. Crops for evidence are copied out explicitly.

### Deployment

- **Edge node (per site):** Jetson Orin or x86 + RTX. Runs the full runtime so a site keeps detecting if the network drops. Docker, read-only root, signed images.
- **Command node:** Aggregates tracks from many edge nodes into one air picture. Hosts operator UI, evidence store, config and model registry.
- **Training environment:** Separate, GPU cluster, Python. Produces versioned model artifacts that edge nodes pull and verify by signature.

---

## 03 · OOP design

The pipeline depends on four narrow interfaces and nothing concrete. Swapping a detector, adding a radar or changing the alert channel is a new class plus one line in the factory, with no edits to the core.

```
«interface»          «interface»          «interface»            «interface»
ISensorSource        IDetector            ITracker               IThreatPolicy
start()/stop()       detect(Frame)        update(Detections,t)   assess(FusedTrack)
subscribe(handler)   warmup() · info()    reset()
   ▲                    ▲                    ▲                      ▲
VideoSource          TrtDetector          ByteTrackTracker       RuleBasedPolicy
RadarSource          OnnxDetector         KalmanIouTracker       LearnedPolicy
RFSource             MotionDetector
                     TiledDetector «decorator»

        wired by Pipeline via dependency injection
Pipeline «orchestrator»          Track «entity · State pattern»       «interface» IAlertSink
addStage · run · stop            Tentative → Confirmed →              emit(Alert)
owns threads, queues,            Coasting → Lost                      C2Sink (CoT, MQTT) · UiSink
backpressure; holds              id · kinematics · class probs        RecorderSink
interfaces only                  sources[] (video, radar, rf)
```

The Pipeline is the only class that knows which concrete types are in use, and it learns that from a factory reading config.

### Patterns and why each is there

| Pattern | Where | What it buys |
|---|---|---|
| Strategy | `IDetector`, `ITracker`, `IThreatPolicy` | Swap algorithms per site or A/B test models with a config change |
| Adapter | Sensor sources | Vendor protocols stay out of the core; one mock per interface for tests |
| Decorator | `TiledDetector` wraps any detector | Small-object tiling added without touching model code |
| Abstract factory + registry | `ComponentRegistry` | Plugins register by name; config picks them at start |
| Observer / pub-sub | Event bus | Recorder, UI and C2 listen to the same tracks independently |
| State | `Track` lifecycle | Confirmation and loss rules live in one place, tested in isolation |
| Supervisor + limp-home | Every socket has a primary and a fallback part | Temporary replacement on fault, shadow-run before switching back or promoting an upgrade |
| Command | PTZ slew-to-cue | Operator and automatic cues share one auditable path |

### Interface sketch

```cpp
// core/include/cuas/detector.hpp
namespace cuas {
struct Detection { BBox box; float score; ClassId cls; };   // pixels, sensor frame

class IDetector {
 public:
  virtual ~IDetector() = default;
  virtual void warmup() = 0;
  virtual std::vector<Detection> detect(const Frame& frame) = 0;
  virtual ModelInfo info() const = 0;
};

class TiledDetector final : public IDetector {   // decorator
 public:
  TiledDetector(std::unique_ptr<IDetector> inner, TileSpec spec);
  std::vector<Detection> detect(const Frame& f) override;  // tile, infer, merge, NMS
};
}  // namespace cuas
```

---

## 04 · Swappable modules

The system is a chassis with sockets, like a car. When a part breaks, a temporary part is fitted so the vehicle keeps running, and the broken one is repaired on the bench. A part can also be upgraded alone. No other part is touched, because parts only meet at the socket.

**Verdict: good for this system, with conditions.** Detector, tracker, sensors and sinks really do fail and change on their own schedule, so isolation pays off. It only works if the socket contracts stay small and stable, and every limp-home part is tested as seriously as the main one.

```
CHASSIS (fixed, rarely changes)
Supervisor · ComponentRegistry · HealthMonitor · Event bus · Config

SOCKETS (versioned interfaces)
ISensorSource   IDetector        ITracker           IFusion            IAlertSink
     │               │                │                  │                  │
PRIMARY PART
RtspSource      TrtDetector      ByteTrackTracker   KalmanFusion       C2Sink (CoT)
[active]        [GPU FAULT]      [active]           [active]           [active]
                     │ failover
LIMP-HOME PART (standby)
BackupRtsp      MotionDetector   KalmanIouTracker   VideoOnlyFusion    LocalLogSink
second stream   CPU · ACTIVE     simple, no re-ID   radar/RF bypassed  buffer + retry
```

The detector socket shows a live swap: the GPU detector is out for repair and a CPU motion detector keeps the site alarming at lower accuracy. The tracker, fusion and sink never notice.

**A limp-home part is not an equal replacement.** `MotionDetector` finds movement but cannot classify objects, so a motion-only site cannot tell a drone from a bird. Degraded mode must therefore be defined per socket: what is lost (classification, radar/RF confirmation, C2 delivery), what the operator sees, and which alert types are still allowed. Alerts raised in degraded mode are tagged "unclassified" and are never auto-confirmed as hostile.

### Failure and recovery rules

`health()` only reports. The Supervisor acts on it with explicit rules. Values are starting points, to be tuned in phase 4.

| Failure | Detected by | Action |
|---|---|---|
| Camera disconnect | No frame for 2 s | Mark source down, reconnect with exponential backoff (1 s up to 30 s), alert operator, keep other cameras running |
| GPU reset or CUDA context error | Inference call error, driver log | Tear down and rebuild the inference context, warm up, resume; if it fails 3 times in 10 min, go to degraded mode |
| Stage hung | No heartbeat for 5 s | Restart the stage; if it is an in-process thread and cannot be stopped, restart the process |
| Queue full for a long time | Drop rate above threshold for 30 s | Raise a warning, then shed load (lower rate or fewer tiles) and tag output as degraded |
| Process crash | Service manager | Restart; reload config and model, rebuild tracks from scratch and mark them "re-acquired" |
| C2 or evidence store unreachable | Send error or timeout | Buffer alerts on local disk, retry with backoff, show the backlog to the operator; never block the frame loop |

**No flapping.** A part that fails is failed over once. Failback needs a minimum dwell time in degraded mode, a clean shadow run (for example 60 s with no errors), and is allowed at most a fixed number of times per hour. After that limit the part is latched out until an operator or an automated repair step clears it. Every transition is written to the audit log.

### MVP scope

Do not build the full framework first. Prove one vertical slice end to end, then widen.

| Build now | Defer until operations show the need |
|---|---|
| Interfaces for `VideoSource`, `IDetector`, `ITracker`, `IFusion`, `IAlertSink` | Plugin registry, abstract factories |
| Video replay adapter, then live camera | Hot-swap of every module |
| Replay regression, structured logging, metrics | General shadow deployment |
| Versioned protobuf schemas | Several implementations per interface |
| Health monitoring, visible degraded-mode status | Distributed event bus for every stage |

Slice: video replay → detector → tracker → alert and evidence → operator UI. Radar and RF are added later, once schemas and calibration exist. Only modules that truly need runtime failover get a limp-home part; the rest change through deployment or config.

### The three garage operations

| Operation | What happens | What stays untouched |
|---|---|---|
| Temporary replacement | HealthMonitor sees missed heartbeats or errors, Supervisor rebinds the socket to the limp-home part, and raises a degraded-mode alert to the operator | Every other module and the event bus |
| Repair the official part | Fix runs on the bench against the replay set and contract tests, then the Supervisor switches back after a warm-up and a short shadow run | The limp-home part keeps serving until the switch |
| Upgrade a part | New model or algorithm registers under a new name or version, runs in shadow beside the old one, then is promoted by config. Rollback is one config line | All other parts, and the socket contract |

### Rules that make it work

- A socket is a small interface plus a message type. The message types (`Frame`, `Detections`, `Track`) are the real bolt pattern, so they live in `proto/` and change rarely.
- Parts never call each other. They publish and consume through the chassis, so one part cannot reach into another.
- Every part implements `health()` and `warmup()` next to its main call, and reports its own mode (full or degraded).
- One shared contract test suite per socket. A part, including a limp-home part, must pass it before it can be registered.
- Shadow mode: a candidate part receives live input and its output is logged and scored, but not used. This is how a repaired or upgraded part is proven.
- Hot swap happens at a frame boundary. Stateful parts (the tracker) export and import state, or the new one starts in a cold-start mode that the UI shows.

```cpp
// core/include/cuas/module.hpp
namespace cuas {
enum class Mode { Full, Degraded, Faulted };

class IModule {                       // every part, in every socket
 public:
  virtual ~IModule() = default;
  virtual void warmup() = 0;
  virtual Health health() const = 0;  // mode, last error, heartbeat age
};

// config: detector: { primary: trt_yolo_v8, fallback: motion_cpu, shadow: trt_rtdetr }
class Supervisor {
 public:
  void bind(SocketId, const BindSpec&);   // primary + fallback + optional shadow
  void failover(SocketId);                // swap at next frame boundary, raise alert
  void failback(SocketId);                // only after warm-up and a clean shadow run
};
}  // namespace cuas
```

### Pros and cons

**Pros**
- A fault stays in one part. A stand-in keeps the site alarming while the real fix is made
- Upgrade one part without regression risk to the rest
- Shadow mode gives A/B model tests on live data
- Parts test alone with fakes; teams work in parallel
- Mixed technology per part (Python prototype, C++ production)
- Vendor lock-in stays inside one adapter

**Cons**
- The socket contract is hard to get right, and a wrong one is costly because every part depends on it
- Frame data crossing a boundary can add copies and latency, so hot-path data needs shared GPU memory
- A generic socket can hide a part's special features (GPU batching, vendor extras)
- Limp-home parts are easy to neglect, and results change silently when failover happens
- More to operate: registry, versions, compatibility matrix, health rules
- Problems between two parts are harder to debug than inside one

### Mitigations built into the plan

- Start with five coarse sockets and add more only when a real need appears.
- Pass frames by reference in GPU memory, never by copy, between the decode, tile and detect parts.
- Every degraded mode is visible to the operator and tagged on each alert, so a lower-accuracy result is never mistaken for a normal one.
- The replay regression set runs against limp-home parts too, with its own lower thresholds.
- Failure injection in phase 4 kills each primary part on purpose and checks the failover.

---

## 05 · Latency budget

Working allocation for glass-to-track on one stream at 1080p with tiling. It is a placeholder to design against, not an acceptance criterion. The stages run in parallel, so 55 ms does not translate to a final frame rate (it would be about 18 fps only if processed strictly one frame at a time).

The budget becomes an acceptance criterion only when these are fixed and measured on the real device:

- GPU model and power mode, camera count, resolution and frame rate
- Tiles per frame and batch size
- Average, p95 and p99 latency, not just the mean
- Throughput with all cameras running at once
- End-to-end latency from camera exposure to the operator receiving the alert

| Stage | Budget |
|---|---|
| Capture + NVDEC decode | 12 ms |
| Preprocess + tile | 6 ms |
| **Inference** | **25 ms** |
| Track | 4 ms |
| Fuse | 5 ms |
| Publish | 3 ms |
| **Total** | **55 ms** |

- Bounded queues between stages with drop-oldest policy. A slow stage drops stale frames; it never builds a backlog.
- Inference dominates, so GPU memory is shared end to end (decode, preprocess and inference without a host copy).
- Timestamp every frame at capture and carry it through to the alert, so latency is measured, not guessed.

---

## 06 · What makes drone detection hard

- **Tiny targets.** A small quadcopter at range is a few to a few dozen pixels. Use tiled inference over full-resolution frames, a stride-4 detection head, long focal length, and train on crops that match the real pixel sizes.
- **Birds and clutter.** Birds, insects, kites and aircraft cause false alarms. Add a second-stage classifier on the track crop, and score motion over time (wingbeat, flight path), not single frames.
- **Day, night, weather.** Pair visible with thermal. Keep one model per modality or a fused-input model, and gate each by image quality metrics.
- **Moving platform.** PTZ and vehicle-mounted cameras move. Estimate ego-motion so the tracker works in world coordinates, and the motion detector subtracts camera movement.
- **Sensor fusion.** Radar gives range and velocity but poor classification; video gives class but no range. Fuse tracks on bearing and time, then confirm hostile class only with video or RF evidence.
- **Metrics that matter.** Probability of detection by range band; false alarms per camera-hour; time from first visible to confirmed track; track continuity (ID switches).

### Evaluation protocol

Detection numbers only mean something if the test data is independent of the training data.

- Split by recording session, and where possible by site, date or condition, never by frame. Neighboring frames of one video must not appear on both sides.
- Keep a held-out set of scenarios that never appear in training (new site, new drone model, night, bad weather).
- Version the labeling guide, the labels, the split and the metric definitions together with the frozen test set.
- Report sample counts and uncertainty with every metric (for example a confidence interval on Pd per range band), not a single value.
- Report false alarms per camera-hour on long background-only recordings, separate from the Pd test set.

### Fusion data contracts

A 2D camera box cannot be matched to a radar track by timestamp alone. Fusion needs:

- A single clock source and measured offset per sensor
- Camera and radar calibration, and coordinate transforms into one frame. For a PTZ camera this includes its pan, tilt and zoom at each frame's timestamp
- Data association between tracks, with handling for late detections, dropped packets and stale tracks
- Uncertainty and evidence source recorded per track

Detector confidence is a score, not the probability that the object is a drone. Keep class probabilities, provenance and uncertainty as separate fields. RF presence on its own is not enough to call a target hostile; it is one piece of evidence with its own bearing error.

Use separate schemas instead of one generic `Track`:

| Schema | Holds |
|---|---|
| `Detection` | timestamp, frame id, sensor id, camera pose (PTZ state), box in pixels, detector score, class scores |
| `SensorTrack` | sensor id, track id, timestamp, last-update age, position and velocity in the sensor frame, covariance |
| `FusedTrack` | global id, timestamp, position and velocity in the world frame, covariance, class probabilities, association state (new, associated, ambiguous, lost), contributing `SensorTrack` ids, evidence list with provenance |

> **Human on the loop.** The platform detects, tracks, classifies and alerts. Any effector or response is a separate system, gated by an operator decision, and every alert carries its evidence clip and the track history that produced it.

---

## 07 · Repository and stack

```
cuas/
├── core/            C++20  interfaces, Track, Pipeline, registry (no vendor deps)
├── sensors/         C++20  VideoSource, RadarSource, RFSource adapters
├── perception/      C++20  TrtDetector, TiledDetector, preprocess (CUDA)
├── tracking/        C++20  Kalman, ByteTrack, FusionEngine
├── decision/        C++20  ThreatAssessor, policies, AlertGateway
├── apps/            C++20  edge_node, command_node (composition roots)
├── proto/                  protobuf schemas = the public contract
├── ml/              Python training, export (ONNX → TensorRT), evaluation
├── tools/           Python replay, dataset tools, simulator, ops API
├── deploy/                 Dockerfiles, compose, Helm, signing
└── tests/                  unit (mock sensors), replay regression, HIL
```

| Layer | Choice | Reason |
|---|---|---|
| Build | CMake + vcpkg or Conan, clang-tidy, sanitizers in CI | Reproducible builds, memory bugs caught early |
| Video and GPU | GStreamer or DeepStream, NVDEC, CUDA, TensorRT | Hardware decode and zero-copy inference |
| Models | YOLO-family or RT-DETR, trained in PyTorch | Mature export path to TensorRT; compare on your own data |
| Messaging | ZeroMQ in-node, DDS or MQTT between nodes, protobuf | Typed contracts, language-neutral |
| Interop standards | ASTERIX for radar, Cursor-on-Target for C2 | Plugs into existing air-defense tooling |
| Observability | Prometheus, Grafana, structured logs | Per-stage latency and detection quality on one screen |
| Security | mTLS, signed images and models, role-based access, audit log | Operational system with sensitive data |
| CI/CD | Replay regression on a fixed video set gates every merge | A model or code change cannot silently lower Pd |

---

## 08 · Roadmap

Durations are indicative for a team of 4–6 and move with data availability.

**Phase 0 · 2–3 weeks — Requirements and data.** Fix the target hardware, cameras and use case. Concept of operations, threat list, required detection ranges, legal and export review. Define the test conditions (range bands, day and night, weather), the independent evaluation data, the labeling method, and numeric acceptance thresholds for Pd, false alarms per camera-hour and latency. Collect drone, bird and background footage from the real sensors.
*Exit: signed requirements with numeric thresholds, and a labeled seed dataset.*
*Gate 1: do not move on without target hardware, usable test data with ground truth, the evaluation protocol, and agreed acceptance criteria.*

**Phase 1 · ~6 weeks — Python vertical slice.** Video replay → detector → tracker → alert and evidence → operator UI, in Python, with replay and evaluation harness, metrics, logging and versioned protobuf schemas. Benchmark on the target hardware.
*Exit: Pd and false-alarm numbers per range band on a frozen test set, plus measured p95/p99 latency and throughput on real hardware.*
*Gate 2: end-to-end demo on target hardware with detection, false-alarm, latency, throughput and replay-regression results. The process/thread model, frame ownership and recovery rules are decided here from the measurements.*

**Phase 2 · duration set by phase 1 benchmark — Port the hot path.** Move only the modules that missed the requirement to C++ (likely decode, preprocess, inference), behind the same interfaces. Add the frame buffer pool and bounded queues.
*Exit: one live stream under the measured requirement, replay regression green.*
*Gate 3: the same workload run before and after each port, comparing accuracy, latency, throughput and resource use. A port that does not improve a missed requirement is reverted.*

**Phase 3 · split into demoable milestones — Sensors, fusion and C2.** Each milestone is demonstrated on its own before the next starts.
- 3a: radar adapter, clock sync and calibration checked with a recorded dataset
- 3b: `SensorTrack` / `FusedTrack` schemas and association, replayed offline
- 3c: RF adapter and evidence-based confirmation
- 3d: PTZ cueing and threat policy
- 3e: alert gateway, C2 integration, operator workflow

Estimates for 3a–3e depend on whether vendor protocols and adapters already exist; do not commit to a date before phase 0 answers that.
*Exit: multi-sensor site demo with operator workflow.*
*Gate 4: each adapter, calibration, association and alert path demonstrated on its own before they are combined.*

**Phase 4 · ~6 weeks — Hardening and field trials.** Hardware-in-the-loop tests on edge hardware, soak tests of 7 days or more, failure injection (lost sensor, GPU reset, network cut), live drone trials in varied weather. Before any field trial: threat model, access control, audit log, command authentication, model and config versioning, recovery after sensor or GPU loss, and the operator alert-confirmation procedure.
*Gate 5: tests pass for camera loss, GPU reset, network partition, C2 unavailable, process restart and degraded mode, and a safe operating procedure is approved. Field trials start only after this.*
*Exit: acceptance against phase 0 requirements.*

**Phase 5 · ongoing — Operate and improve.** Collect hard cases from the field, retrain, ship signed models with versioning and rollback, track model drift and the false-alarm rate.

The roadmap is a rough estimate, not a schedule commitment, until the open questions below are answered.

---

## 09 · Main risks

| Risk | Impact | Mitigation |
|---|---|---|
| Too little real drone footage at long range | High | Early field collection, synthetic data for augmentation only, test set always from real sensors |
| False alarms from birds erode operator trust | High | Second-stage classifier, temporal scoring, per-site threshold tuning, report false alarms per hour from day one |
| Model accuracy drops after a change | Medium | Frozen replay set gating CI, model registry with rollback |
| Vendor lock-in on GPU or camera SDK | Medium | All vendor code behind adapters; ONNX kept as the portable model format |
| C++ team ramp-up | Medium | Keep the C++ surface small (the frame loop), enforce sanitizers and clang-tidy, Python for all other work |
| Limp-home part drifts or is never tested | High | Same contract tests and replay set as primaries, degraded mode shown on every alert, scheduled failover drills |
| Socket contract set wrong early | Medium | Few coarse sockets, versioned messages, freeze the contract only after the phase 1 baseline |
| Regulatory and export limits | Medium | Review in phase 0, keep model and data handling auditable |
| Framework built before the model and data are proven | High | Vertical slice first; registry, hot-swap and shadow deployment only on demonstrated need |
| Latency target never validated on real hardware | High | Fix hardware and workload in phase 0, report p95/p99 from the phase 1 benchmark |
| Fusion without calibration or clock sync | High | Calibration and timestamp checks per sensor before any association work |
| Degraded mode mistaken for normal accuracy | High | Per-socket degraded-mode definition, alerts tagged "unclassified", no auto-confirm |

---

## 10 · Open questions before approving the full implementation

1. Is the target hardware Jetson Orin or x86 with an NVIDIA RTX GPU? How many cameras, at what resolution and frame rate?
2. Does the MVP only detect and alert, or does it also need PTZ cueing and C2 integration?
3. Is there real footage with ground truth, especially at long range and at night?
4. What are the acceptance thresholds for latency, false alarms, detection performance and simultaneous cameras? These have no values yet and must be agreed with stakeholders from the use case and sensor limits. Until then phase 1 cannot be declared a success and no schedule is committed.
5. Which modules need runtime failover or independent operation, and which only need to change through deployment or config?
