#pragma once

#include <cstddef>
#include <vector>

#include "uavsd/core/types.hpp"

namespace uavsd {

struct ScoredBox {
    BoundingBox box;
    int classId = 0;
    float score = 0.0F;
};

[[nodiscard]] std::vector<std::size_t> nonMaxSuppression(const std::vector<ScoredBox>& boxes,
                                                         double iouThreshold);

}
