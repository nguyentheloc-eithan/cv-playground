# UAVs Defense — Development Plan

This plan turns the roadmap in the README into concrete, ordered work. It assumes a solo developer working roughly **8–10 hours per week** with access to one CUDA GPU (local or cloud). Durations are estimates; the order matters more than the dates.

---

## Guiding Principles

1. **Vertical slice first.** Get a simple pipeline working end to end (video → detection → tracking → display) before optimizing any single stage.
2. **Measure before changing.** Every improvement is compared against a recorded baseline on the frozen test set.
3. **Change one thing at a time.** One variable per experiment, so you know what caused the result.
4. **Keep the engine replaceable.** Nothing outside `ai/engines/` imports Ultralytics directly.
5. **Record everything.** Model, weights, dataset version, config, code commit, hardware, and results for every run.
6. **Protect the test set.** Tune on validation only. Touch the test set only for milestone reports.

---

## Timeline Overview

| Phase | Name                               | Est. duration | Cumulative |
| ----- | ---------------------------------- | ------------- | ---------- |
| 0     | Project setup                      | 1 week        | week 1     |
| 1     | Dataset                            | 2–3 weeks     | week 4     |
| 2     | Engine abstraction + YOLO engine   | 1–2 weeks     | week 5     |
| 3     | Baseline fine-tuning               | 2 weeks       | week 7     |
| 4     | Tracking                           | 2–3 weeks     | week 10    |
| 5     | Small-UAV improvements             | 3 weeks       | week 13    |
| 6     | Engine comparison                  | 2–3 weeks     | week 16    |
| 7     | Optimization                       | 2 weeks       | week 18    |
| 8     | Localization                       | 2 weeks       | week 20    |
| 9     | Backend + web visualization        | 3 weeks       | week 23    |
| 10    | Simulation                         | 3–4 weeks     | week 27    |
| 11+   | 3D visualization, fusion, hardware | open-ended    | —          |

**Minimum viable result (around week 10):** a fine-tuned YOLO model that detects and tracks UAVs in a recorded video, with measured detection and tracking metrics.

---

## Phase 0 — Project Setup (week 1)

**Goal:** A clean, reproducible repository.

- [ ] Create the repository with the structure from the README
- [ ] Add `LICENSE` (AGPL-3.0)
- [ ] Create `requirements.txt` (pin major versions) and a virtual environment
- [ ] Verify PyTorch sees the GPU: `python -c "import torch; print(torch.cuda.is_available())"`
- [ ] Add `.gitignore` for datasets, weights, videos, and run outputs
- [ ] Set up formatting and linting (e.g., `ruff`) and `pytest`
- [ ] Create `configs/` with YAML config loading
- [ ] Add a basic logging setup
- [ ] Optional: choose experiment tracking (TensorBoard is enough to start)

**Done when:** a fresh clone can install dependencies and run `pytest` successfully.

---

## Phase 1 — Dataset (weeks 2–4)

**Goal:** One unified, well-documented UAV dataset in YOLO format.

### Tasks

- [ ] Pick **2–3 datasets** to start (for example, one detection-focused dataset, one tracking dataset with video sequences, and one with birds as confusers)
- [ ] Read and record each dataset's license and terms in `datasets/SOURCES.md`
- [ ] Write one converter script per dataset → YOLO format (`class cx cy w h`, normalized)
- [ ] Map all drone labels to a single class: `uav`
- [ ] Write a **visual check script** that draws labels on random images; inspect at least 100 samples per source
- [ ] Remove broken, empty, or mislabeled samples
- [ ] Add hard negatives: bird, aircraft, and empty-sky images with empty label files
- [ ] Split **by sequence/recording**: roughly 70 / 15 / 15 train / val / test
- [ ] Write `data.yaml`
- [ ] Write a dataset statistics script:
  - number of images and boxes per split
  - box size histogram (tiny < 16 px, small < 32 px, medium, large)
  - number of images with multiple UAVs
  - background type coverage where available
- [ ] Tag this as dataset version `uav_v1`

### Tips

- Video datasets have many near-identical frames. Subsample (for example, every 5th–10th frame) for training to save time without losing much.
- Keep a small, fixed set of **full test videos** separate for tracking evaluation in Phase 4.

**Done when:** `uav_v1` exists, the visual check looks correct, and the stats report shows the size distribution.

---

## Phase 2 — Engine Abstraction + YOLO Engine (weeks 4–5)

**Goal:** Run detection on a video through the common interface.

### Tasks

- [ ] Implement `ai/engines/base.py`: `BoundingBox`, `Detection`, `DetectionEngine` protocol
- [ ] Implement `ai/engines/registry.py`: build an engine from config
- [ ] Implement `ai/engines/yolo/engine.py`:
  - load weights
  - warm up with a dummy frame
  - run inference and convert results to `list[Detection]`
- [ ] Implement `inference/sources.py`: video file, webcam, and RTSP frame sources yielding `(frame, frame_index, timestamp)`
- [ ] Implement `inference/video.py`: read → detect → draw boxes → write output video
- [ ] Unit tests:
  - adapter output types and coordinate conversions
  - empty-frame behavior (no detections)
- [ ] Run with a **pretrained COCO YOLO model** on a UAV video just to confirm the pipeline works

### Note

COCO has no "drone" class, so pretrained results will be poor or mislabeled (for example, as "bird" or "airplane"). That is expected. This phase is about plumbing, not accuracy.

**Done when:** `python -m inference.video --source demo.mp4` produces an annotated output video, and no code outside `ai/engines/yolo/` imports Ultralytics.

---

## Phase 3 — Baseline Fine-Tuning (weeks 5–7)

**Goal:** A first UAV-trained YOLO model with honest metrics.

### Experiments

| Run | Model   | imgsz | Purpose                            |
| --- | ------- | ----- | ---------------------------------- |
| B1  | YOLO26n | 640   | Fast sanity check                  |
| B2  | YOLO26s | 640   | Baseline                           |
| B3  | YOLO26s | 1280  | Resolution effect on small UAVs    |
| B4  | YOLO11s | 1280  | Stable-version fallback comparison |

### Tasks

- [ ] Train B1 for a short run first to confirm loss decreases and labels are correct
- [ ] Train B2–B4 with fixed seeds and identical settings except the tested variable
- [ ] Write `ai/evaluation/detection.py`:
  - precision, recall, mAP@50, mAP@50-95
  - **recall and AP per size bucket**
  - false positives on negative (bird/aircraft) images
- [ ] Measure inference latency on your GPU
- [ ] Review failure cases visually: save the worst false negatives and false positives
- [ ] Pick a **confidence threshold** from the precision–recall curve on validation
- [ ] Create `models/benchmarks/results.csv` and log every run

### Experiment Log Columns

```text
run_id, date, engine, model, weights, dataset_version, imgsz, epochs,
seed, git_commit, precision, recall, map50, map50_95,
recall_tiny, recall_small, fp_per_neg_image, latency_ms, gpu, notes
```

**Done when:** the best baseline is identified, its metrics are logged, and you have a written list of the main failure patterns.

---

## Phase 4 — Tracking (weeks 7–10)

**Goal:** Stable track IDs, measured with standard metrics.

### Step 1: Quick prototype

- [ ] Use Ultralytics' built-in ByteTrack and BoT-SORT on test videos
- [ ] Visually compare: ID switches, lost tracks, behavior when a UAV briefly disappears

### Step 2: Detector-independent tracker

- [ ] Implement `ai/tracking/base.py`: `Track` type and `Tracker` protocol consuming `list[Detection]`
- [ ] Integrate a standalone ByteTrack implementation (or write your own)
- [ ] Add track states: tentative → confirmed → lost → removed
- [ ] Compute per-track velocity from the Kalman filter state
- [ ] Draw track IDs and short trajectory trails on output video

### Step 3: Evaluation

- [ ] Convert tracking ground truth for your test videos to MOT format
- [ ] Evaluate with TrackEval: **HOTA, MOTA, IDF1, ID switches**
- [ ] Tune: track buffer length, match thresholds, minimum hits to confirm, low-confidence detection handling

**Done when:** the full pipeline (video → detections → tracks → annotated video) works, tracking metrics are logged, and switching the engine in config does not break tracking.

> This is the **minimum viable result**. Record a demo video here.

---

## Phase 5 — Small-UAV Improvements (weeks 10–13)

**Goal:** Measurably better detection of tiny and distant UAVs.

Run each as a separate experiment against the Phase 3 baseline:

| Exp | Change                                                  | Watch for                         |
| --- | ------------------------------------------------------- | --------------------------------- |
| S1  | Tiled/sliced inference (e.g., SAHI)                     | Recall gain vs. latency cost      |
| S2  | P2 (stride-4) detection head via custom model YAML      | Tiny-object recall, training cost |
| S3  | Augmentation tuning (scale, mosaic, copy-paste)         | Overfitting                       |
| S4  | More hard negatives                                     | Bird/aircraft false positives     |
| S5  | Tracker-based confirmation of low-confidence detections | Recall gain without FP increase   |
| S6  | Larger model (m) at 1280                                | Accuracy vs. speed trade-off      |

### Tasks

- [ ] Run S1–S6, logging each in `results.csv`
- [ ] Combine only the changes that helped, and verify the combination
- [ ] Write `docs/benchmark.md` section: "Small-UAV improvements" with a results table and conclusions

**Done when:** tiny/small UAV recall improved over baseline with an acceptable latency cost, and the reasoning is documented.

---

## Phase 6 — Engine Comparison (weeks 13–16)

**Goal:** A fair, documented comparison of detection engines.

### Tasks

- [ ] Implement `ai/engines/rtdetr/` (official repo or Ultralytics-provided RT-DETR)
- [ ] Implement `ai/engines/yolox/`
- [ ] Convert the dataset to each engine's required format (COCO JSON is common)
- [ ] Train each on `uav_v1` with comparable budgets and resolution
- [ ] Evaluate all with **your own evaluation script** on common `Detection[]` output, so the scoring is identical
- [ ] Measure latency on the same GPU with the same input size
- [ ] Run each through the same tracker and compare HOTA / IDF1
- [ ] Write `docs/model-selection.md`: results table, trade-offs, and the chosen default engine

**Done when:** the default engine is chosen based on your measurements, and changing engines requires only a config edit.

---

## Phase 7 — Optimization (weeks 16–18)

**Goal:** Real-time performance.

### Tasks

- [ ] Export the selected model to ONNX; verify outputs match PyTorch
- [ ] Export to TensorRT FP16 (NVIDIA); verify accuracy
- [ ] Optional: INT8 with calibration data; check small-UAV recall carefully, as quantization often hurts tiny objects most
- [ ] Add exported-model engines (`OnnxEngine`, `TensorRTEngine`) behind the same interface
- [ ] Profile the whole pipeline: decode, preprocess, inference, tracking, drawing
- [ ] Move slow stages to separate threads if needed (for example, frame reading)
- [ ] Record: FPS, end-to-end latency, memory, model size for each format

**Done when:** the pipeline runs in real time on your target video resolution, with accuracy loss documented.

---

## Phase 8 — Localization (weeks 18–20)

**Goal:** Convert tracks into bearings and approximate ranges.

### Tasks

- [ ] Calibrate your camera with a checkerboard using OpenCV; save intrinsics and distortion
- [ ] Implement pixel → undistorted normalized coordinates → azimuth/elevation
- [ ] Add camera orientation config to convert to world-referenced bearing
- [ ] Implement known-size range estimation with uncertainty
- [ ] Add bearing and range to `Track`
- [ ] Unit test with synthetic points where the correct answer is known

**Done when:** each confirmed track reports bearing (and optional range), and tests pass. Full accuracy validation happens in Phase 10.

---

## Phase 9 — Backend + Web Visualization (weeks 20–23)

**Goal:** View live tracks in a browser.

### Tasks

- [ ] FastAPI backend:
  - `GET /health`
  - `GET /config` (current engine, thresholds)
  - `POST /sources` (start a video file or stream)
  - `WS /tracks` (stream track updates as JSON)
- [ ] Define a versioned JSON message schema for tracks
- [ ] Run the perception pipeline in a background worker, separate from the API
- [ ] Web frontend:
  - video view with boxes and track IDs
  - track list with confidence, velocity, bearing
  - basic performance display (FPS, latency)
- [ ] Optional: MJPEG or WebRTC video streaming

**Done when:** you can open a browser, start a video, and watch tracks update live.

---

## Phase 10 — Simulation (weeks 23–27)

**Goal:** Validate tracking and localization against exact ground truth.

### Tasks

- [ ] Set up Gazebo + PX4 SITL (optionally with ROS 2)
- [ ] Add a simulated camera and one or more simulated UAVs with scripted trajectories
- [ ] Add a simulation frame source to `inference/sources.py`
- [ ] Log ground-truth UAV positions with timestamps
- [ ] Measure bearing and range error against ground truth
- [ ] Test scenarios: crossing paths, multiple UAVs, fast turns, targets leaving and re-entering view
- [ ] Note the sim-to-real gap: simulated imagery looks different, so fine-tune or evaluate carefully

**Done when:** localization and tracking errors are measured in repeatable scenarios and documented.

---

## Phase 11+ — Extensions

- **3D visualization:** show camera position, bearing rays, and estimated positions in a 3D web view (for example, three.js)
- **Simulated multi-sensor fusion:** add simulated radar/RF measurements and fuse with camera tracks using an Extended Kalman Filter and track-to-track association
- **Edge deployment:** run the optimized engine on Jetson-class hardware
- **Physical sensor integration:** real cameras, then other sensors when available

---

## Risks and Mitigations

| Risk                               | Mitigation                                                                |
| ---------------------------------- | ------------------------------------------------------------------------- |
| Data leakage inflates scores       | Split by sequence; keep test set frozen                                   |
| Tiny UAVs remain undetectable      | Higher resolution, tiling, P2 head, temporal confirmation                 |
| Birds cause false positives        | Hard negatives; per-confuser FP metrics                                   |
| Not enough GPU time                | Start with n/s models, subsample video frames, use cloud GPU for big runs |
| Engine lock-in                     | Enforce "no Ultralytics imports outside `ai/engines/yolo/`"               |
| Scope creep                        | Finish the minimum viable result (Phase 4) before starting extensions     |
| Dataset license limits             | Record terms in `SOURCES.md` before use                                   |
| Plans change toward commercial use | Re-evaluate licensing; switch default to an Apache-2.0 engine if needed   |

---

## Milestone Checklist

- [ ] **M1 (week 5):** Pipeline runs on video through the common interface
- [ ] **M2 (week 7):** First fine-tuned UAV detector with logged metrics
- [ ] **M3 (week 10):** Detection + tracking demo with HOTA/IDF1 — minimum viable result
- [ ] **M4 (week 16):** Engine comparison report and chosen default
- [ ] **M5 (week 18):** Real-time optimized pipeline
- [ ] **M6 (week 23):** Live web visualization with bearings
- [ ] **M7 (week 27):** Simulation-validated localization and tracking
