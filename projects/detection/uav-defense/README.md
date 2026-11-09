# UAVs Defense

## AI-Based UAV Detection, Localization & Tracking System

> **UAVs Defense** is a personal AI research project focused on the real-time detection, identification, localization, and continuous tracking of Unmanned Aerial Vehicles (UAVs) using computer vision.

**Project type:** Personal, non-commercial research project
**License:** AGPL-3.0 (see [License & Third-Party Components](#license--third-party-components))
**Primary detection engine:** Ultralytics YOLO (YOLO26 / YOLO11)
**Comparison engines:** RT-DETR / RT-DETRv2, YOLOX
**Status:** Early development (see [Development Roadmap](#development-roadmap))

The implementation is **software-first**. It relies on public UAV datasets, recorded video, and software simulation as its data sources, so the full perception pipeline can be built and evaluated without dedicated sensing hardware.

The system is built around a **replaceable AI detection engine**. Ultralytics YOLO is the primary engine because of its mature training, tracking, and export tooling, but the rest of the application never depends on YOLO-specific objects. Any detector can be plugged in, benchmarked, or swapped without rewriting tracking, localization, or visualization.

The architecture is designed to later incorporate **EO/IR, radar, and RF/SDR** sensing when physical hardware becomes available.

---

## Table of Contents

1. [Overview](#overview)
2. [Project Objectives](#project-objectives)
3. [Current Scope](#current-scope)
4. [System Architecture](#system-architecture)
5. [UAV Detection Pipeline](#uav-detection-pipeline)
6. [AI Detection Engine](#ai-detection-engine)
7. [Detection Engine Interface](#detection-engine-interface)
8. [Small-UAV Detection Strategy](#small-uav-detection-strategy)
9. [Multi-Object Tracking](#multi-object-tracking)
10. [UAV Localization](#uav-localization)
11. [Data Sources & Simulation](#data-sources--simulation)
12. [Dataset & Model Training](#dataset--model-training)
13. [Performance Evaluation](#performance-evaluation)
14. [Software Requirements](#software-requirements)
15. [Quick Start](#quick-start)
16. [Project Structure](#project-structure)
17. [Development Roadmap](#development-roadmap)
18. [Future Multi-Sensor Integration](#future-multi-sensor-integration)
19. [Research Direction](#research-direction)
20. [Core Concept](#core-concept)
21. [License & Third-Party Components](#license--third-party-components)

---

# Overview

Small UAVs are a hard computer-vision problem. A distant UAV may occupy only a few pixels, and its appearance changes with viewing angle, lighting, background, motion blur, compression, and weather. It is also easily confused with birds, aircraft, and background clutter.

A reliable UAV perception system must handle:

- Small-object detection
- Real-time inference
- Multiple simultaneous targets
- Target identity preservation
- Temporary detection loss
- Motion and trajectory estimation
- Environmental variation
- Spatial localization
- Limited compute resources

```text
                  Public Dataset / Video
                           │
                           ▼
                   Frame Acquisition
                           │
                           ▼
                   Image Preprocessing
                           │
                           ▼
                ┌───────────────────────┐
                │   AI Detection Engine │
                │                       │
                │ YOLO (primary)        │
                │ RT-DETR / YOLOX       │
                │ Custom Model          │
                └───────────┬───────────┘
                            │
                            ▼
                     UAV Detections
                            │
                            ▼
                   Multi-Object Tracking
                            │
                            ▼
                  Target State Estimation
                            │
                            ▼
                     UAV Localization
                            │
                            ▼
                      UAV Track Output
```

---

# Project Objectives

The project aims to build a complete UAV perception pipeline that can:

- Detect UAVs in images, recorded video, and live streams
- Detect multiple UAVs simultaneously with calibrated confidence scores
- Distinguish UAVs from common confusers such as birds and aircraft
- Maintain persistent target identities across frames
- Estimate target motion and trajectory
- Estimate target bearing and approximate position
- Evaluate detection and tracking quantitatively with standard metrics
- Compare detection engines under a fair, repeatable protocol
- Run in real time on a desktop GPU and, later, on edge hardware
- Provide an architecture ready for future multi-sensor fusion

The focus is **UAV perception**: detection, tracking, and localization. UAV mitigation and interception are out of scope.

---

# Current Scope

## In Scope

- UAV image and video processing
- Dataset collection, conversion, and preparation
- YOLO fine-tuning for UAV detection
- Small-object detection improvements
- Detection-engine abstraction and benchmarking
- Multi-object tracking and track evaluation
- Image-based bearing and range estimation
- Model export and runtime optimization
- Web-based visualization
- Software simulation for ground-truth experiments

## Data Sources

- Public UAV detection and tracking datasets
- Public UAV videos
- Personally recorded video
- Synthetic and simulated data

## Future Hardware (not assumed available)

- EO/IR cameras
- Radar systems
- SDR / RF sensors
- Other aerial sensing systems

---

# System Architecture

The application is split into independent stages so each can be tested and improved on its own.

```text
┌─────────────────────────────────────────────────────────────────┐
│                         UAVs DEFENSE                            │
│                  AI-Based UAV Perception System                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Dataset / Video / Simulation / Live Stream                    │
│             │                                                   │
│             ▼                                                   │
│   Frame Source  ──────────────  (file, RTSP, webcam, sim)       │
│             │                                                   │
│             ▼                                                   │
│   Preprocessing ──────────────  (resize, tiling, normalization) │
│             │                                                   │
│             ▼                                                   │
│   ┌──────────────────────────────────────┐                      │
│   │          AI Detection Engine         │                      │
│   │  YOLO (primary) │ RT-DETR │ YOLOX    │                      │
│   │  Custom / Exported (ONNX, TensorRT)  │                      │
│   └──────────────────┬───────────────────┘                      │
│                      │  Detection[]  (common format)            │
│                      ▼                                          │
│   Multi-Object Tracker ───────  (ByteTrack / BoT-SORT)          │
│                      │  Track[]                                 │
│                      ▼                                          │
│   State Estimation ───────────  (Kalman filter)                 │
│                      │                                          │
│                      ▼                                          │
│   Localization ───────────────  (bearing, range estimate)       │
│                      │                                          │
│                      ▼                                          │
│   Output ─────────────────────  (API, WebSocket, video, logs)   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

# UAV Detection Pipeline

```text
Input (image / video / stream)
        │
        ▼
Frame Extraction  ── frame_index, timestamp
        │
        ▼
Preprocessing
        │
        ▼
Detection Engine
        │
        ▼
Detection[]
        ├── bounding box
        ├── class
        ├── confidence
        └── timestamp
        │
        ▼
Tracker
        │
        ▼
Track[]
        ├── track_id
        ├── position (image + estimated world)
        ├── velocity
        └── state (tentative / confirmed / lost)
        │
        ▼
Localization / Visualization / API
```

The same detection output contract is used for every model.

---

# AI Detection Engine

## Design Principle

The detector is a **replaceable engine**, not the application itself. Any engine can be used as a baseline, fine-tuned, optimized, exported, modified, or replaced.

```text
                    Detection Engine
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   Ultralytics YOLO     RT-DETR           YOLOX
      (primary)       (comparison)     (comparison)
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                  Common Detection[]
                           ▼
                     Tracking Layer
```

## Primary Engine: Ultralytics YOLO

Ultralytics YOLO is the primary engine for this project because it offers:

- Simple fine-tuning on custom datasets
- Multiple model sizes (n, s, m, l, x) to trade accuracy against speed
- Built-in trackers (ByteTrack, BoT-SORT) for fast prototyping
- Export to ONNX, TensorRT, OpenVINO, and other runtimes
- Strong documentation and community support

The project starts with **YOLO26** (the current Ultralytics release) and keeps **YOLO11** as a stable fallback. Newer Ultralytics releases can be added as additional engines and benchmarked under the same protocol.

Ultralytics YOLO is used under **AGPL-3.0**, which fits this personal, open-source project. See [License & Third-Party Components](#license--third-party-components).

## Comparison Engines

| Engine              | Why it is included                                           | License                    |
| ------------------- | ------------------------------------------------------------ | -------------------------- |
| RT-DETR / RT-DETRv2 | Transformer-based, NMS-free, strong accuracy baseline        | Apache-2.0 (official repo) |
| YOLOX               | Anchor-free real-time CNN detector, independent codebase     | Apache-2.0                 |
| Custom model        | UAV-specific architecture changes (e.g., small-object heads) | Project license            |

## Model Selection Principle

YOLO is the starting point, not a final verdict. The engine used by default is whichever performs best on this project's UAV test set and target hardware, with particular weight on **small-UAV recall** and **end-to-end latency**.

```text
Candidate Engines
      │
      ▼
Same dataset split + same evaluation protocol
      │
      ├── mAP@50, mAP@50-95
      ├── Precision / Recall
      ├── Small-UAV recall
      ├── False positives on birds / aircraft
      ├── Latency / FPS
      └── Memory / model size
      │
      ▼
Default Engine  →  fine-tune → optimize → replace when justified
```

---

# Detection Engine Interface

The application consumes **common detections**, never model-specific inference objects.

```python
from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class BoundingBox:
    x: float        # top-left x, pixels
    y: float        # top-left y, pixels
    width: float    # pixels
    height: float   # pixels


@dataclass(frozen=True)
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    frame_index: int
    timestamp: float  # seconds since stream start


class DetectionEngine(Protocol):
    name: str

    def load(self, model_path: str) -> None: ...

    def warmup(self) -> None: ...

    def detect(
        self, frame: np.ndarray, frame_index: int, timestamp: float
    ) -> list[Detection]: ...

    def close(self) -> None: ...
```

Each engine has an adapter that converts native output into `Detection[]`:

```text
Model Output  →  Engine Adapter  →  list[Detection]
```

Engines are selected by configuration, not by code changes:

```yaml
# configs/engine.yaml
engine: yolo # yolo | rtdetr | yolox | custom
weights: models/checkpoints/yolo26s_uav_v1.pt
imgsz: 1280
conf_threshold: 0.25
device: cuda:0
```

---

# Small-UAV Detection Strategy

Small and distant UAVs are the hardest part of this project. The following techniques are evaluated one at a time, and each result is recorded in the benchmark log:

| Technique                       | Idea                                                                           |
| ------------------------------- | ------------------------------------------------------------------------------ |
| Higher input resolution         | Train and infer at 1280 px instead of 640 px so small targets keep more pixels |
| Tiled / sliced inference        | Split large frames into overlapping tiles (e.g., SAHI) and merge detections    |
| High-resolution detection head  | Add a stride-4 (P2) output layer for tiny objects via a custom model YAML      |
| Small-object-aware augmentation | Tune mosaic/scale augmentation; copy-paste small UAVs onto new backgrounds     |
| Hard negatives                  | Include birds, aircraft, insects, and clutter labeled as background            |
| Temporal cues                   | Use the tracker to confirm weak detections that persist across frames          |
| Threshold tuning                | Choose confidence thresholds from the precision–recall curve, not defaults     |

Performance is always reported **per object size**, not only as a single mAP value.

---

# Multi-Object Tracking

Detection answers _what is in this frame_. Tracking answers _which object is which over time_.

```text
Frame N detections ─┐
                    ├─► Association (motion + IoU + confidence) ─► Track 01, 02, 03
Frame N+1 detections┘
```

## Approach

1. **Prototype:** use the Ultralytics built-in trackers (ByteTrack, BoT-SORT) for a quick end-to-end demo.
2. **Decouple:** move to a detector-independent tracker that consumes `list[Detection]` (for example, a standalone ByteTrack implementation), so tracking works with every engine.
3. **Improve:** tune the Kalman motion model and association thresholds for small, fast, erratically moving UAVs.

## Track Model

```text
Track
├── track_id
├── class_name
├── confidence          (smoothed)
├── bbox                (latest)
├── center_px           (x, y)
├── velocity_px         (vx, vy per second)
├── bearing             (azimuth, elevation, when calibrated)
├── range_estimate      (optional, with uncertainty)
├── first_seen / last_seen
├── hits / misses
└── state               (tentative | confirmed | lost)
```

---

# UAV Localization

The detector works in **image coordinates**. Converting to physical quantities requires camera information.

## Level 1: Bearing (single calibrated camera)

With camera intrinsics (focal lengths `fx, fy`, principal point `cx, cy`) from OpenCV calibration, a pixel `(u, v)` maps to a viewing direction:

```text
azimuth   ≈ atan((u - cx) / fx)
elevation ≈ atan((cy - v) / fy)
```

These angles are relative to the camera. Adding the camera's known orientation converts them to world-referenced bearings.

## Level 2: Approximate Range

A single camera cannot measure distance directly. Range can be approximated from:

- **Known target size:** `range ≈ fx × real_width / pixel_width` (very sensitive to size assumptions and box accuracy)
- **Known or assumed altitude** combined with elevation angle
- **Simulation ground truth** for validating estimates

Every range estimate is reported with its uncertainty.

## Level 3: 3D Position (future)

- Multiple cameras (triangulation)
- Camera + radar or RF fusion

In the current software-based implementation, localization accuracy is validated in simulation, where true positions are known.

---

# Data Sources & Simulation

## Public UAV Datasets (candidates)

The following datasets contain UAVs **as targets** (as opposed to imagery taken _from_ drones, such as VisDrone, which is not suitable here):

| Dataset                            | Content                                                        |
| ---------------------------------- | -------------------------------------------------------------- |
| Anti-UAV (Anti-UAV300 / 410 / 600) | RGB and thermal IR tracking sequences                          |
| Drone-vs-Bird Detection Challenge  | Videos with drones and birds as confusers                      |
| DUT Anti-UAV                       | Detection images and tracking sequences                        |
| Det-Fly                            | Air-to-air UAV detection images                                |
| MAV-VID                            | Videos of small multirotor UAVs                                |
| Halmstad Drone Detection Dataset   | IR and visible video with drones, birds, aircraft, helicopters |

Each dataset has its own license and terms of use (many are research-only). Terms are checked and recorded in `datasets/SOURCES.md` before use.

## Recorded and Synthetic Data

- Personally recorded videos for real-world testing
- Synthetic images (UAVs composited onto varied backgrounds)
- Simulated scenes with exact ground-truth position and velocity

## Simulation

Gazebo with PX4 SITL (optionally through ROS 2) provides repeatable scenarios with a simulated camera and known UAV trajectories. This is used to validate tracking and localization end to end.

---

# Dataset & Model Training

## Preparation Steps

1. Download and document each source dataset
2. Convert all annotations to a single YOLO-format dataset
3. Start with **one class** (`uav`), and add sub-classes later if useful
4. Add **hard-negative** images (birds, aircraft, empty sky)
5. Split data **by video sequence**, never by individual frame
6. Freeze the test split and never use it for tuning
7. Analyze object-size distribution and class balance

> Splitting by frame leaks nearly identical images between train and test and produces unrealistically high scores. Always split by sequence or recording.

## Structure

```text
datasets/
├── raw/                 # original downloads, untouched
├── processed/
│   └── uav_v1/
│       ├── images/{train,val,test}/
│       ├── labels/{train,val,test}/
│       └── data.yaml
├── splits/              # sequence-level split lists
└── SOURCES.md           # origin, license, and version of each dataset
```

## Dataset Should Cover

- Small and distant UAVs
- Multiple resolutions and viewing angles
- Sky, urban, vegetation, cloud, and haze backgrounds
- Motion blur and compression artifacts
- Different lighting, including dawn and dusk
- Partial occlusion
- Multiple simultaneous UAVs
- Birds and aircraft as confusers

## Training Example

```bash
yolo detect train \
  model=yolo26s.pt \
  data=datasets/processed/uav_v1/data.yaml \
  imgsz=1280 epochs=100 batch=8 seed=42 \
  project=models/runs name=yolo26s_uav_v1
```

---

# Performance Evaluation

## Detection Metrics

| Metric                    | Description                                    |
| ------------------------- | ---------------------------------------------- |
| Precision                 | Share of predicted UAVs that are correct       |
| Recall                    | Share of real UAVs that were detected          |
| mAP@50                    | Average precision at IoU 0.50                  |
| mAP@50-95                 | Average precision across IoU 0.50–0.95         |
| AP / Recall by size       | Tiny (< 16 px), small (< 32 px), medium, large |
| False positives per frame | Especially on bird and aircraft sequences      |

## Runtime Metrics

| Metric             | Description                 |
| ------------------ | --------------------------- |
| Inference latency  | Model forward pass time     |
| End-to-end latency | Frame in → track out        |
| FPS                | Sustained frames per second |
| GPU / CPU memory   | Resource usage              |
| Model size         | Deployed file size          |

## Tracking Metrics

| Metric              | Description                                                      |
| ------------------- | ---------------------------------------------------------------- |
| HOTA                | Balanced detection + association quality                         |
| MOTA                | Overall tracking accuracy (misses, false positives, ID switches) |
| IDF1                | Identity consistency over time                                   |
| ID switches         | Number of identity changes                                       |
| Track fragmentation | How often a real track is broken                                 |

## Localization Metrics (simulation)

| Metric        | Description                          |
| ------------- | ------------------------------------ |
| Bearing error | Angle difference from ground truth   |
| Range error   | Absolute and relative distance error |

## Benchmark Protocol

All engines are compared with the same dataset split, input resolution policy, hardware, thresholds, evaluation scripts, and video sequences. Every experiment records model, weights, code version, dataset version, and license in `models/benchmarks/`.

---

# Software Requirements

## Operating System

- Ubuntu 22.04 / 24.04
- Windows 11 + WSL2

## Core

- Python 3.10+
- PyTorch (CUDA build when a GPU is available)
- Ultralytics
- OpenCV
- NumPy
- ONNX / ONNX Runtime

## Evaluation

- Ultralytics validation / pycocotools (detection)
- TrackEval (tracking)

## Application

- FastAPI + WebSocket (backend)
- Web frontend (e.g., React or plain HTML/JS)

## Optional

- TensorRT (NVIDIA deployment)
- SAHI (sliced inference)
- ROS 2, Gazebo, PX4 SITL (simulation)
- Experiment tracking (MLflow, TensorBoard, or similar)

## Hardware

A CUDA GPU is recommended for training. Inference can run on CPU for development. Later deployment targets include desktop GPUs and NVIDIA Jetson-class edge devices.

---

# Quick Start

> Commands below describe the intended workflow and will be finalized as the implementation matures.

```bash
# 1. Clone and set up the environment
git clone <repo-url> uavs-defense
cd uavs-defense
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Prepare the dataset
python scripts/prepare_dataset.py --config configs/dataset.yaml

# 3. Train the YOLO engine
python scripts/train.py --config configs/train_yolo.yaml

# 4. Run detection + tracking on a video
python -m inference.video --source data/samples/demo.mp4 --config configs/engine.yaml

# 5. Evaluate
python scripts/evaluate.py --engine yolo --split test
```

---

# Project Structure

```text
uavs-defense/
│
├── ai/
│   ├── engines/
│   │   ├── base.py             # DetectionEngine protocol + Detection types
│   │   ├── registry.py         # engine selection from config
│   │   ├── yolo/               # Ultralytics YOLO engine (primary)
│   │   ├── rtdetr/             # comparison engine
│   │   ├── yolox/              # comparison engine
│   │   └── custom/
│   ├── tracking/
│   │   ├── base.py             # Tracker protocol + Track types
│   │   ├── bytetrack/
│   │   └── kalman.py
│   ├── localization/
│   │   ├── calibration.py
│   │   └── bearing.py
│   └── evaluation/
│       ├── detection.py
│       ├── tracking.py
│       └── runtime.py
│
├── configs/                    # engine, dataset, training, tracker configs
├── datasets/                   # raw, processed, splits, SOURCES.md
├── models/
│   ├── checkpoints/
│   ├── exports/                # ONNX, TensorRT
│   └── benchmarks/             # experiment results
├── inference/
│   ├── sources.py              # file, webcam, RTSP, simulation
│   ├── video.py
│   └── stream.py
├── backend/
│   ├── api/
│   └── websocket/
├── frontend/
│   └── web/
├── simulation/
├── scripts/
├── tests/
├── docs/
│   ├── architecture.md
│   ├── development-plan.md
│   ├── model-selection.md
│   └── benchmark.md
├── LICENSE                     # AGPL-3.0
├── requirements.txt
└── README.md
```

Large files (datasets, weights, videos) are kept out of Git.

---

# Development Roadmap

The project follows a **vertical-slice** strategy: build one simple working pipeline end to end first, then improve each stage.

> **Build → Measure → Improve → Compare → Optimize → Extend**

| Phase | Focus                            | Outcome                                                    |
| ----- | -------------------------------- | ---------------------------------------------------------- |
| 0     | Project setup                    | Repo, environment, license, configs, tests                 |
| 1     | Dataset                          | Unified YOLO-format UAV dataset with sequence-level splits |
| 2     | Engine abstraction + YOLO engine | Detection on video through the common interface            |
| 3     | Baseline fine-tuning             | First UAV-trained YOLO model with size-based metrics       |
| 4     | Tracking                         | Persistent track IDs, evaluated with HOTA / IDF1           |
| 5     | Small-UAV improvements           | Measured gains from resolution, tiling, P2 head, negatives |
| 6     | Engine comparison                | YOLO vs. RT-DETR vs. YOLOX benchmark report                |
| 7     | Optimization                     | ONNX / TensorRT export, real-time performance              |
| 8     | Localization                     | Calibrated bearing and approximate range                   |
| 9     | Backend + web visualization      | Live tracks in a browser                                   |
| 10    | Simulation                       | Ground-truth validation of tracking and localization       |
| 11    | 3D visualization                 | Tracks shown in a 3D scene                                 |
| 12    | Simulated multi-sensor fusion    | Fusion architecture tested with simulated sensors          |
| 13    | Physical sensor integration      | Real hardware, when available                              |

The detailed plan, with tasks and completion criteria for each phase, is in [`docs/development-plan.md`](docs/development-plan.md).

---

# Future Multi-Sensor Integration

```text
                         UAV
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
         EO / IR        Radar       RF / SDR
             │            │            │
             └────────────┼────────────┘
                          ▼
                   Data Association
                          ▼
                    Sensor Fusion
                          ▼
                       UAV Track
```

These sensors are future work. Research areas include radar–camera fusion, RF–camera correlation, track-to-track association, Extended Kalman Filtering, confidence fusion, and multi-modal classification.

---

# Research Direction

The project sits at the intersection of computer vision, object detection, multi-object tracking, geometric localization, sensor fusion, real-time computing, and edge AI.

**Central research question:**

> How can modern AI-based computer vision achieve accurate, robust, real-time UAV detection and tracking under varying environmental and operational conditions?

```text
Raw Image / Video → UAV Detection → Multi-Object Tracking
→ Position & Motion Estimation → UAV Track → Situational Awareness
```

---

# Core Concept

The detector is an **engine**, not the entire vehicle.

```text
DATA ─► DETECT ─► TRACK ─► LOCALIZE ─► ANALYZE ─► VISUALIZE
           │
           └── Replaceable AI Engine
               ├── Ultralytics YOLO (primary)
               ├── RT-DETR / RT-DETRv2
               ├── YOLOX
               └── Custom / Optimized Model
```

> **Choose an engine → build a baseline → train it for UAVs → benchmark it → optimize it → replace it when a stronger approach is justified.**

---

# License & Third-Party Components

This is a **personal, non-commercial, open-source research project** released under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

AGPL-3.0 was chosen because the primary detection engine, **Ultralytics YOLO**, is distributed under AGPL-3.0. Models fine-tuned from Ultralytics weights are treated as covered by the same license.

| Component          | License                                             |
| ------------------ | --------------------------------------------------- |
| Ultralytics YOLO   | AGPL-3.0 (Enterprise license available)             |
| RT-DETR (official) | Apache-2.0                                          |
| YOLOX              | Apache-2.0                                          |
| Datasets           | Individual terms, recorded in `datasets/SOURCES.md` |

Apache-2.0 components are compatible with inclusion in this AGPL-3.0 project.

**If the project's purpose changes** (for example, closed-source distribution or commercial use), licensing will be re-evaluated before release. Options include an Ultralytics Enterprise license or switching the default engine to an Apache-2.0 detector, which the engine abstraction makes straightforward.

References:

- Ultralytics documentation and licensing: https://docs.ultralytics.com/
- RT-DETR official repository: https://github.com/lyuwenyu/RT-DETR
- YOLOX official repository: https://github.com/Megvii-BaseDetection/YOLOX

---

> **UAVs Defense — from AI-powered visual detection to real-time UAV situational awareness.**
