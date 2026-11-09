#pragma once

#include <cstdint>
#include <span>
#include <vector>

#include "uavsd/core/letterbox.hpp"
#include "uavsd/core/nms.hpp"

namespace uavsd {

enum class YoloOutputFormat { Auto, EndToEnd, Raw };

[[nodiscard]] YoloOutputFormat resolveYoloOutputFormat(YoloOutputFormat requested,
                                                       std::span<const std::int64_t> shape);

[[nodiscard]] std::vector<ScoredBox> decodeYoloEndToEnd(std::span<const float> data,
                                                        std::int64_t rows, float confThreshold,
                                                        const LetterboxInfo& letterbox);

[[nodiscard]] std::vector<ScoredBox> decodeYoloRaw(std::span<const float> data,
                                                   std::int64_t channels, std::int64_t anchors,
                                                   float confThreshold, double iouThreshold,
                                                   const LetterboxInfo& letterbox);

}
