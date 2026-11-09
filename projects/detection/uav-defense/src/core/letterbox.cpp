#include "uavsd/core/letterbox.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace uavsd {

LetterboxInfo computeLetterbox(int sourceWidth, int sourceHeight, int inputSize) {
    if (sourceWidth <= 0 || sourceHeight <= 0 || inputSize <= 0) {
        throw std::invalid_argument("letterbox dimensions must be positive");
    }
    LetterboxInfo info;
    info.sourceWidth = sourceWidth;
    info.sourceHeight = sourceHeight;
    info.inputSize = inputSize;
    info.scale = std::min(static_cast<double>(inputSize) / sourceWidth,
                          static_cast<double>(inputSize) / sourceHeight);
    const double resizedWidth = std::round(sourceWidth * info.scale);
    const double resizedHeight = std::round(sourceHeight * info.scale);
    info.padX = std::floor((inputSize - resizedWidth) / 2.0);
    info.padY = std::floor((inputSize - resizedHeight) / 2.0);
    return info;
}

BoundingBox unletterbox(const LetterboxInfo& info, double x1, double y1, double x2, double y2) {
    const auto maxX = static_cast<double>(info.sourceWidth);
    const auto maxY = static_cast<double>(info.sourceHeight);
    const double left = std::clamp((x1 - info.padX) / info.scale, 0.0, maxX);
    const double top = std::clamp((y1 - info.padY) / info.scale, 0.0, maxY);
    const double right = std::clamp((x2 - info.padX) / info.scale, 0.0, maxX);
    const double bottom = std::clamp((y2 - info.padY) / info.scale, 0.0, maxY);
    return BoundingBox{left, top, std::max(0.0, right - left), std::max(0.0, bottom - top)};
}

}
