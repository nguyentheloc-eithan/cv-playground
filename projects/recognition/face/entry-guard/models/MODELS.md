# Models

Put files in this folder (git-ignored). Names are set in `config/default.yaml` under `models:`.

| Stage | File | Source | Licence |
|---|---|---|---|
| Detector (YuNet) | `yunet.onnx` | OpenCV Zoo: `face_detection_yunet_2023mar.onnx` | MIT |
| Embedder (SFace) | `sface.onnx` | OpenCV Zoo: `face_recognition_sface_2021dec.onnx` | Apache-2.0 |

Download from https://github.com/opencv/opencv_zoo (folders `models/face_detection_yunet`
and `models/face_recognition_sface`) and rename, or set the file names in your customer config.
