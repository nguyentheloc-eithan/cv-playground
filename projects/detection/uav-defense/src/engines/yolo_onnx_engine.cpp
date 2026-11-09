#include "uavsd/engines/yolo_onnx_engine.hpp"

#include <array>
#include <cmath>
#include <map>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>

#include <onnxruntime_cxx_api.h>
#include <opencv2/imgproc.hpp>

#include "uavsd/core/letterbox.hpp"
#include "uavsd/core/metadata.hpp"
#include "uavsd/core/yolo_decode.hpp"

namespace uavsd {

namespace {

constexpr int kPadValue = 114;

int parseCudaDeviceId(const std::string& device) {
    const auto colon = device.find(':');
    return colon == std::string::npos ? 0 : std::stoi(device.substr(colon + 1));
}

}

struct YoloOnnxEngine::Impl {
    Ort::Env env{ORT_LOGGING_LEVEL_WARNING, "uavsd"};
    std::optional<Ort::Session> session;
    std::string inputName;
    std::string outputName;
    int inputSize = 0;
    std::map<int, std::string> classNames;
    std::vector<float> inputBuffer;
    cv::Mat resized;
    cv::Mat padded;
    cv::Mat rgb;
    cv::Mat normalized;
};

YoloOnnxEngine::YoloOnnxEngine(EngineConfig config)
    : config_(std::move(config)), impl_(std::make_unique<Impl>()) {}

YoloOnnxEngine::~YoloOnnxEngine() = default;

std::string_view YoloOnnxEngine::name() const { return "yolo"; }

void YoloOnnxEngine::load(const std::filesystem::path& modelPath) {
    if (!std::filesystem::exists(modelPath)) {
        throw std::runtime_error("model file not found: " + modelPath.string());
    }

    Ort::SessionOptions options;
    options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
    if (config_.device.rfind("cuda", 0) == 0) {
        OrtCUDAProviderOptions cuda{};
        cuda.device_id = parseCudaDeviceId(config_.device);
        options.AppendExecutionProvider_CUDA(cuda);
    }

    impl_->session.emplace(impl_->env, modelPath.c_str(), options);
    Ort::Session& session = *impl_->session;
    Ort::AllocatorWithDefaultOptions allocator;

    if (session.GetInputCount() != 1 || session.GetOutputCount() < 1) {
        throw std::runtime_error("unexpected YOLO model inputs/outputs");
    }
    impl_->inputName = session.GetInputNameAllocated(0, allocator).get();
    impl_->outputName = session.GetOutputNameAllocated(0, allocator).get();

    const auto inputShape = session.GetInputTypeInfo(0).GetTensorTypeAndShapeInfo().GetShape();
    if (inputShape.size() != 4) {
        throw std::runtime_error("expected NCHW model input");
    }
    impl_->inputSize = inputShape[2] > 0 ? static_cast<int>(inputShape[2]) : config_.imgsz;
    impl_->inputBuffer.assign(
        static_cast<std::size_t>(3 * impl_->inputSize * impl_->inputSize), 0.0F);

    impl_->classNames = config_.classNames;
    if (impl_->classNames.empty()) {
        const Ort::ModelMetadata metadata = session.GetModelMetadata();
        if (auto names = metadata.LookupCustomMetadataMapAllocated("names", allocator)) {
            impl_->classNames = parseClassNames(names.get());
        }
    }
}

void YoloOnnxEngine::warmup() {
    if (!impl_->session) {
        throw std::logic_error("warmup called before load");
    }
    const cv::Mat dummy(impl_->inputSize, impl_->inputSize, CV_8UC3, cv::Scalar::all(kPadValue));
    static_cast<void>(detect(dummy, -1, 0.0));
}

std::vector<Detection> YoloOnnxEngine::detect(const cv::Mat& frame, std::int64_t frameIndex,
                                              double timestamp) {
    if (!impl_->session) {
        throw std::logic_error("detect called before load");
    }
    if (frame.empty()) {
        return {};
    }

    const int size = impl_->inputSize;
    const LetterboxInfo letterbox = computeLetterbox(frame.cols, frame.rows, size);
    const int resizedWidth = static_cast<int>(std::lround(frame.cols * letterbox.scale));
    const int resizedHeight = static_cast<int>(std::lround(frame.rows * letterbox.scale));
    const int padLeft = static_cast<int>(letterbox.padX);
    const int padTop = static_cast<int>(letterbox.padY);

    cv::resize(frame, impl_->resized, cv::Size(resizedWidth, resizedHeight), 0.0, 0.0,
               cv::INTER_LINEAR);
    cv::copyMakeBorder(impl_->resized, impl_->padded, padTop, size - resizedHeight - padTop,
                       padLeft, size - resizedWidth - padLeft, cv::BORDER_CONSTANT,
                       cv::Scalar::all(kPadValue));
    cv::cvtColor(impl_->padded, impl_->rgb, cv::COLOR_BGR2RGB);
    impl_->rgb.convertTo(impl_->normalized, CV_32FC3, 1.0 / 255.0);

    const auto plane = static_cast<std::size_t>(size * size);
    std::vector<cv::Mat> channels{
        cv::Mat(size, size, CV_32FC1, impl_->inputBuffer.data()),
        cv::Mat(size, size, CV_32FC1, impl_->inputBuffer.data() + plane),
        cv::Mat(size, size, CV_32FC1, impl_->inputBuffer.data() + 2 * plane)};
    cv::split(impl_->normalized, channels);

    const std::array<std::int64_t, 4> inputShape{1, 3, size, size};
    const Ort::MemoryInfo memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    Ort::Value input = Ort::Value::CreateTensor<float>(memory, impl_->inputBuffer.data(),
                                                       impl_->inputBuffer.size(),
                                                       inputShape.data(), inputShape.size());

    const char* inputNames[] = {impl_->inputName.c_str()};
    const char* outputNames[] = {impl_->outputName.c_str()};
    auto outputs =
        impl_->session->Run(Ort::RunOptions{nullptr}, inputNames, &input, 1, outputNames, 1);

    const auto shape = outputs[0].GetTensorTypeAndShapeInfo().GetShape();
    const std::size_t count = outputs[0].GetTensorTypeAndShapeInfo().GetElementCount();
    const std::span<const float> data(outputs[0].GetTensorData<float>(), count);

    std::vector<ScoredBox> boxes;
    switch (resolveYoloOutputFormat(config_.outputFormat, shape)) {
        case YoloOutputFormat::EndToEnd:
            boxes = decodeYoloEndToEnd(data, shape[1], config_.confThreshold, letterbox);
            break;
        case YoloOutputFormat::Raw:
        case YoloOutputFormat::Auto:
            boxes = decodeYoloRaw(data, shape[1], shape[2], config_.confThreshold,
                                  config_.iouThreshold, letterbox);
            break;
    }

    std::vector<Detection> detections;
    detections.reserve(boxes.size());
    for (const ScoredBox& box : boxes) {
        const auto name = impl_->classNames.find(box.classId);
        detections.push_back(Detection{
            box.classId,
            name != impl_->classNames.end() ? name->second : "class_" + std::to_string(box.classId),
            box.score, box.box, frameIndex, timestamp});
    }
    return detections;
}

void YoloOnnxEngine::close() { impl_->session.reset(); }

}
