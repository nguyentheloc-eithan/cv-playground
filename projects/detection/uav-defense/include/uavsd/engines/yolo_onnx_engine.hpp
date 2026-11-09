#pragma once

#include <memory>

#include "uavsd/config/engine_config.hpp"
#include "uavsd/engines/detection_engine.hpp"

namespace uavsd {

class YoloOnnxEngine final : public DetectionEngine {
public:
    explicit YoloOnnxEngine(EngineConfig config);
    ~YoloOnnxEngine() override;

    YoloOnnxEngine(const YoloOnnxEngine&) = delete;
    YoloOnnxEngine& operator=(const YoloOnnxEngine&) = delete;

    [[nodiscard]] std::string_view name() const override;

    void load(const std::filesystem::path& modelPath) override;

    void warmup() override;

    [[nodiscard]] std::vector<Detection> detect(const cv::Mat& frame, std::int64_t frameIndex,
                                                double timestamp) override;

    void close() override;

private:
    struct Impl;
    EngineConfig config_;
    std::unique_ptr<Impl> impl_;
};

}
