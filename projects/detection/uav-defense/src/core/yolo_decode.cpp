#include "uavsd/core/yolo_decode.hpp"

#include <stdexcept>

namespace uavsd {

namespace {

constexpr std::int64_t kEndToEndColumns = 6;
constexpr std::int64_t kBoxChannels = 4;

}

YoloOutputFormat resolveYoloOutputFormat(YoloOutputFormat requested,
                                         std::span<const std::int64_t> shape) {
    if (shape.size() != 3) {
        throw std::runtime_error("expected a 3D YOLO output tensor");
    }
    if (requested != YoloOutputFormat::Auto) {
        return requested;
    }
    if (shape[2] == kEndToEndColumns && shape[1] != kEndToEndColumns) {
        return YoloOutputFormat::EndToEnd;
    }
    return YoloOutputFormat::Raw;
}

std::vector<ScoredBox> decodeYoloEndToEnd(std::span<const float> data, std::int64_t rows,
                                          float confThreshold, const LetterboxInfo& letterbox) {
    if (rows < 0 || data.size() < static_cast<std::size_t>(rows * kEndToEndColumns)) {
        throw std::invalid_argument("end-to-end output buffer is too small");
    }
    std::vector<ScoredBox> result;
    for (std::int64_t row = 0; row < rows; ++row) {
        const auto base = static_cast<std::size_t>(row * kEndToEndColumns);
        const float score = data[base + 4];
        if (score < confThreshold) {
            continue;
        }
        BoundingBox box = unletterbox(letterbox, data[base], data[base + 1], data[base + 2],
                                      data[base + 3]);
        if (box.area() <= 0.0) {
            continue;
        }
        result.push_back(ScoredBox{box, static_cast<int>(data[base + 5]), score});
    }
    return result;
}

std::vector<ScoredBox> decodeYoloRaw(std::span<const float> data, std::int64_t channels,
                                     std::int64_t anchors, float confThreshold,
                                     double iouThreshold, const LetterboxInfo& letterbox) {
    if (channels <= kBoxChannels || anchors < 0 ||
        data.size() < static_cast<std::size_t>(channels * anchors)) {
        throw std::invalid_argument("raw output buffer does not match its shape");
    }
    const auto at = [&](std::int64_t channel, std::int64_t anchor) {
        return data[static_cast<std::size_t>(channel * anchors + anchor)];
    };

    std::vector<ScoredBox> candidates;
    for (std::int64_t anchor = 0; anchor < anchors; ++anchor) {
        int bestClass = -1;
        float bestScore = confThreshold;
        for (std::int64_t channel = kBoxChannels; channel < channels; ++channel) {
            const float score = at(channel, anchor);
            if (score >= bestScore) {
                bestScore = score;
                bestClass = static_cast<int>(channel - kBoxChannels);
            }
        }
        if (bestClass < 0) {
            continue;
        }
        const double cx = at(0, anchor);
        const double cy = at(1, anchor);
        const double halfW = at(2, anchor) / 2.0;
        const double halfH = at(3, anchor) / 2.0;
        BoundingBox box = unletterbox(letterbox, cx - halfW, cy - halfH, cx + halfW, cy + halfH);
        if (box.area() <= 0.0) {
            continue;
        }
        candidates.push_back(ScoredBox{box, bestClass, bestScore});
    }

    std::vector<ScoredBox> result;
    for (std::size_t index : nonMaxSuppression(candidates, iouThreshold)) {
        result.push_back(candidates[index]);
    }
    return result;
}

}
