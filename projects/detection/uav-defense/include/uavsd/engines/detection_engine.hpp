#pragma once

#include <cstdint>
#include <filesystem>
#include <string_view>
#include <vector>

#include <opencv2/core/mat.hpp>

#include "uavsd/core/types.hpp"

namespace uavsd {

class DetectionEngine {
public:
    virtual ~DetectionEngine() = default;

    [[nodiscard]] virtual std::string_view name() const = 0;

    virtual void load(const std::filesystem::path& modelPath) = 0;

    virtual void warmup() = 0;

    [[nodiscard]] virtual std::vector<Detection> detect(const cv::Mat& frame,
                                                        std::int64_t frameIndex,
                                                        double timestamp) = 0;

    virtual void close() = 0;
};

}
