#include "uavsd/core/nms.hpp"

#include <algorithm>
#include <numeric>

namespace uavsd {

std::vector<std::size_t> nonMaxSuppression(const std::vector<ScoredBox>& boxes,
                                           double iouThreshold) {
    std::vector<std::size_t> order(boxes.size());
    std::iota(order.begin(), order.end(), std::size_t{0});
    std::stable_sort(order.begin(), order.end(), [&boxes](std::size_t a, std::size_t b) {
        return boxes[a].score > boxes[b].score;
    });

    std::vector<std::size_t> kept;
    std::vector<bool> suppressed(boxes.size(), false);
    for (std::size_t i = 0; i < order.size(); ++i) {
        const std::size_t current = order[i];
        if (suppressed[current]) {
            continue;
        }
        kept.push_back(current);
        for (std::size_t j = i + 1; j < order.size(); ++j) {
            const std::size_t candidate = order[j];
            if (suppressed[candidate] || boxes[candidate].classId != boxes[current].classId) {
                continue;
            }
            if (intersectionOverUnion(boxes[current].box, boxes[candidate].box) > iouThreshold) {
                suppressed[candidate] = true;
            }
        }
    }
    return kept;
}

}
