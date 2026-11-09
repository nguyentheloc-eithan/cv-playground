# Models (not in git)

| File | Job | Source (OpenCV Zoo) |
|---|---|---|
| `yunet.onnx` | find faces | `face_detection_yunet_2023mar.onnx` |
| `sface.onnx` | face to numbers | `face_recognition_sface_2021dec.onnx` |

```
curl -L -o models/yunet.onnx https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
curl -L -o models/sface.onnx https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
```
Check the sizes: yunet is about 230 KB, sface about 37 MB. A tiny file is an error page.
