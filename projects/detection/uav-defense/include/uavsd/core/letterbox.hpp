#pragma once

#include "uavsd/core/types.hpp"

namespace uavsd {

struct LetterboxInfo {
    double scale = 1.0;
    double padX = 0.0;
    double padY = 0.0;
    int sourceWidth = 0;
    int sourceHeight = 0;
    int inputSize = 0;
};

[[nodiscard]] LetterboxInfo computeLetterbox(int sourceWidth, int sourceHeight, int inputSize);

[[nodiscard]] BoundingBox unletterbox(const LetterboxInfo& info, double x1, double y1, double x2,
                                      double y2);

}
